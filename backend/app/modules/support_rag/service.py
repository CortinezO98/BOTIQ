import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_document import KnowledgeDocument
from app.services.gdrive_service import gdrive_service
from app.services.vertex.embeddings_service import embeddings_service
from app.services.vertex.gemini_text_service import gemini_text_service

RAG_SYSTEM = """Eres BOTIQ en modo Ingeniero de Soporte.

Base de conocimiento disponible:
{knowledge_context}

Alcance:
- Procedimientos técnicos corporativos
- Diagnóstico de aplicativos, URLs, servicios, certificados, red, servidores, backups y bases de datos
- Guías internas indexadas desde Google Drive
- Soporte a ingenieros para recordar pasos a seguir

Reglas:
1. Responde SOLO con base en el contexto y la información operativa interna recibida.
2. Cita fuentes cuando uses documentos.
3. Si el contexto no es suficiente, dilo claramente.
4. Da pasos numerados y accionables.
5. No respondas temas ajenos al negocio ni información no relacionada con IQ.
6. Si se debe escalar, explica qué validaciones ya se deberían tener antes de crear ticket.
"""



TECH_STOPWORDS = {
    "hola", "estoy", "intentando", "usando", "formula", "fórmula", "problema", "resultado",
    "columna", "llena", "numeros", "números", "como", "simplemente", "porque", "pasa", "soluciono",
    "solución", "usuario", "error", "abrir", "puedo", "tengo", "sale", "ayuda", "iq", "botiq"
}


def _query_terms(text: str) -> set[str]:
    import re
    terms = set()
    for t in re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_]{3,}", (text or "").lower()):
        if t not in TECH_STOPWORDS:
            terms.add(t)
    return terms


def _has_meaningful_overlap(query: str, chunks: List[Dict]) -> bool:
    """Evita usar RAG cuando Chroma trae documentos internos no relacionados."""
    terms = _query_terms(query)
    if not terms:
        return True

    combined = "\n".join(
        f"{c.get('source','')} {c.get('content','')[:1200]}" for c in (chunks or [])[:3]
    ).lower()
    hits = [t for t in terms if t in combined]
    return len(hits) >= (2 if len(terms) >= 5 else 1)


NO_KNOWLEDGE = (
    "No encontré información suficiente en la base de conocimiento corporativa.\n\n"
    "Antes de escalar, recomiendo:\n"
    "1. Confirmar URL/IP o aplicativo afectado.\n"
    "2. Validar estado del servicio si existe en la API de estados.\n"
    "3. Revisar error exacto, fecha/hora, usuario afectado y evidencia.\n"
    "4. Agregar documentación sobre este tema a Google Drive si es recurrente."
)


class SupportRAGService:
    def __init__(self):
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ──────────────────────────────────────────────────────────────────
    #  Extracción de texto y utilidades
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    async def _extract_text(self, doc: Dict) -> str:
        """Devuelve el texto de un documento.

        PDF:
        1. Intenta extracción local con pypdf para PDF digitales.
        2. Si no encuentra texto, intenta Document AI para PDF escaneados/imágenes.
        """
        if doc.get("doc_type") == "pdf" and doc.get("bytes"):
            pdf_bytes = doc["bytes"]

            # 1) PDF digital: extracción local
            try:
                import io
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(pdf_bytes))
                pages = []
                for idx, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(f"[Página {idx}]\n{text.strip()}")

                local_text = "\n\n".join(pages).strip()
                if local_text:
                    return local_text
            except Exception as exc:
                print(f"⚠️  PDF local extraction error en {doc.get('name')}: {exc}")

            # 2) PDF escaneado / imagen: Document AI
            try:
                from app.services.vertex.document_ai_service import document_ai_service

                text = await document_ai_service.process_pdf(pdf_bytes)
                if text and text.strip():
                    return text.strip()
            except Exception as exc:
                print(f"⚠️  Document AI extraction error en {doc.get('name')}: {exc}")

            return ""

        return doc.get("content", "")

    def _delete_chunks_for_file(self, collection, file_id: str):
        """Elimina de ChromaDB todos los chunks de un documento (por metadata)."""
        try:
            collection.delete(where={"file_id": file_id})
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  No se pudieron borrar chunks previos de {file_id}: {exc}")

    async def _index_document(self, collection, doc: Dict, text: str) -> int:
        """Crea embeddings y hace upsert de los chunks de un documento. Devuelve nº de chunks."""
        chunks = self._chunk_text(text)
        # Limpia versiones anteriores antes de reindexar (evita chunks huérfanos).
        self._delete_chunks_for_file(collection, doc["file_id"])

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc['file_id']}_chunk_{i}"
            embedding = await embeddings_service.embed_text(chunk)
            collection.upsert(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "file_id": doc["file_id"],
                    "file_name": doc["name"],
                    "doc_type": doc.get("doc_type", ""),
                    "modified_at": doc.get("modified_at", ""),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }],
            )
        return len(chunks)

    # ──────────────────────────────────────────────────────────────────
    #  Sincronización incremental
    # ──────────────────────────────────────────────────────────────────

    async def sync_knowledge_base(self, db: AsyncSession, force: bool = False) -> Dict:
        """
        Sincroniza la base de conocimiento desde Google Drive de forma INCREMENTAL.

        - Procesa solo documentos nuevos o cuyo contenido cambió (hash distinto),
          salvo que force=True (reindexa todo).
        - Marca como 'skipped' los que no cambiaron (sin gastar embeddings).
        - Elimina de ChromaDB y de la tabla los documentos que ya no están en Drive.
        - Guarda estado, nº de chunks y errores por documento en knowledge_documents.
        """
        if not gdrive_service.is_configured():
            return {
                "status": "error",
                "message": "Google Drive no configurado. Verifica GDRIVE_FOLDER_ID / GDRIVE_FOLDER_IDS y service-account.json",
                "documents_processed": 0,
            }

        documents = await gdrive_service.get_all_documents_content_with_type()
        collection = self._get_collection()

        # Índice de registros existentes por file_id.
        existing_rows = (await db.execute(select(KnowledgeDocument))).scalars().all()
        by_file = {row.file_id: row for row in existing_rows}
        drive_file_ids = set()

        indexed, updated, skipped, errors = 0, 0, 0, 0

        for doc in documents:
            file_id = doc["file_id"]
            drive_file_ids.add(file_id)
            row = by_file.get(file_id)

            try:
                text = await self._extract_text(doc)
                if not text.strip():
                    print(f"⚠️  {doc['name']}: sin contenido extraíble")
                    self._upsert_doc_record(
                        db, row, doc, content_hash=None, chunk_count=0,
                        status="failed", error="Sin contenido extraíble",
                    )
                    errors += 1
                    continue

                new_hash = self._hash_text(text)
                unchanged = (
                    row is not None
                    and row.status == "indexed"
                    and row.content_hash == new_hash
                )

                if unchanged and not force:
                    # No cambió: no se reindexa (ahorra embeddings).
                    self._touch_doc_record(row, status="indexed")
                    skipped += 1
                    print(f"⏭️  {doc['name']}: sin cambios, omitido")
                    continue

                chunk_count = await self._index_document(collection, doc, text)
                self._upsert_doc_record(
                    db, row, doc, content_hash=new_hash, chunk_count=chunk_count,
                    status="indexed", error=None, mark_indexed=True,
                )
                if row is None:
                    indexed += 1
                    print(f"✅ {doc['name']}: {chunk_count} chunks indexados (nuevo)")
                else:
                    updated += 1
                    print(f"♻️  {doc['name']}: {chunk_count} chunks reindexados")

            except Exception as exc:  # noqa: BLE001
                print(f"❌ Error procesando {doc.get('name')}: {exc}")
                self._upsert_doc_record(
                    db, row, doc, content_hash=None, chunk_count=(row.chunk_count if row else 0),
                    status="failed", error=str(exc),
                )
                errors += 1

        # Documentos que estaban indexados pero ya NO están en Drive → eliminar.
        removed = 0
        for file_id, row in by_file.items():
            if file_id not in drive_file_ids:
                self._delete_chunks_for_file(collection, file_id)
                await db.delete(row)
                removed += 1
                print(f"🗑️  {row.file_name}: eliminado (ya no está en Drive)")

        await db.commit()

        return {
            "status": "success",
            "mode": "full" if force else "incremental",
            "documents_in_drive": len(documents),
            "indexed_new": indexed,
            "reindexed": updated,
            "skipped_unchanged": skipped,
            "removed": removed,
            "errors": errors,
            "total_chunks": collection.count(),
        }

    async def reindex_document(self, db: AsyncSession, file_id: str) -> Dict:
        """Reindexa un único documento por su file_id (botón 'reindexar' del frontend)."""
        if not gdrive_service.is_configured():
            return {"status": "error", "message": "Google Drive no configurado"}

        documents = await gdrive_service.get_all_documents_content_with_type()
        doc = next((d for d in documents if d["file_id"] == file_id), None)
        if not doc:
            return {"status": "not_found", "message": "Documento no encontrado en Drive"}

        collection = self._get_collection()
        row = (
            await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.file_id == file_id))
        ).scalar_one_or_none()

        try:
            text = await self._extract_text(doc)
            if not text.strip():
                self._upsert_doc_record(db, row, doc, content_hash=None, chunk_count=0, status="failed", error="Sin contenido extraíble")
                await db.commit()
                return {"status": "failed", "message": "Sin contenido extraíble"}

            chunk_count = await self._index_document(collection, doc, text)
            self._upsert_doc_record(
                db, row, doc, content_hash=self._hash_text(text), chunk_count=chunk_count,
                status="indexed", error=None, mark_indexed=True,
            )
            await db.commit()
            return {"status": "indexed", "file_name": doc["name"], "chunk_count": chunk_count, "total_chunks": collection.count()}
        except Exception as exc:  # noqa: BLE001
            self._upsert_doc_record(db, row, doc, content_hash=None, chunk_count=(row.chunk_count if row else 0), status="failed", error=str(exc))
            await db.commit()
            return {"status": "failed", "message": str(exc)}

    async def list_documents(self, db: AsyncSession) -> List[Dict]:
        """Lista los documentos registrados con su estado, para el frontend."""
        rows = (
            await db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.file_name))
        ).scalars().all()
        return [
            {
                "file_id": r.file_id,
                "file_name": r.file_name,
                "doc_type": r.doc_type,
                "chunk_count": r.chunk_count or 0,
                "status": r.status,
                "error_message": r.error_message,
                "drive_modified_at": r.drive_modified_at,
                "last_indexed_at": r.last_indexed_at.isoformat() if r.last_indexed_at else None,
            }
            for r in rows
        ]

    # ── Helpers de persistencia del registro por documento ──────────────

    def _upsert_doc_record(
        self,
        db: AsyncSession,
        row: Optional[KnowledgeDocument],
        doc: Dict,
        content_hash: Optional[str],
        chunk_count: int,
        status: str,
        error: Optional[str],
        mark_indexed: bool = False,
    ):
        now = datetime.now(timezone.utc)
        if row is None:
            row = KnowledgeDocument(file_id=doc["file_id"])
            db.add(row)
        row.file_name = doc["name"]
        row.doc_type = doc.get("doc_type")
        row.mime_type = doc.get("mime_type")
        row.drive_modified_at = doc.get("modified_at")
        row.content_hash = content_hash if content_hash is not None else row.content_hash
        row.chunk_count = chunk_count
        row.status = status
        row.error_message = error
        if mark_indexed:
            row.last_indexed_at = now
        row.updated_at = now

    @staticmethod
    def _touch_doc_record(row: KnowledgeDocument, status: str):
        row.status = status
        row.updated_at = datetime.now(timezone.utc)

    # ──────────────────────────────────────────────────────────────────
    #  Recuperación y generación (sin cambios de comportamiento)
    # ──────────────────────────────────────────────────────────────────

    async def retrieve_context(self, query: str, top_k: int = None) -> List[Dict]:
        top_k = top_k or settings.RAG_TOP_K
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []

            emb = await embeddings_service.embed_text(query)
            results = collection.query(
                query_embeddings=[emb],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                    chunks.append({
                        "content": doc,
                        "source": meta.get("file_name", "Desconocido"),
                        "relevance_score": max(0.0, 1 - dist),
                    })

            chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
            return chunks
        except Exception as exc:  # noqa: BLE001
            print(f"ChromaDB error: {exc}")
            return []

    async def generate_response(
        self,
        user_message: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        q = f"{user_message}\nContexto visual: {image_analysis}" if image_analysis else user_message
        chunks = await self.retrieve_context(q)
        avg_conf = sum(c["relevance_score"] for c in chunks) / len(chunks) if chunks else 0.0
        best_conf = max((c["relevance_score"] for c in chunks), default=0.0)

        if (
            not chunks
            or best_conf < settings.RAG_MIN_CONFIDENCE
            or not _has_meaningful_overlap(user_message, chunks)
        ):
            return {
                "text": NO_KNOWLEDGE,
                "sources": [],
                "avg_confidence": avg_conf,
                "best_confidence": best_conf,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
            }

        context = "\n\n---\n\n".join([f"[Fuente: {c['source']}]\n{c['content']}" for c in chunks])
        result = await gemini_text_service.generate(
            prompt=q,
            system_instruction=RAG_SYSTEM.format(knowledge_context=context),
            history=history,
            temperature=0.2,
            max_output_tokens=max(settings.MAX_OUTPUT_TOKENS, 1536),
            model=settings.VERTEX_REASONING_MODEL,
        )

        if not result.get("success", True):
            return {
                "text": NO_KNOWLEDGE,
                "tokens_used": result.get("tokens_used") or 0,
                "response_time_ms": result.get("response_time_ms") or 0,
                "sources": list({c["source"] for c in chunks}),
                "avg_confidence": avg_conf,
                "best_confidence": best_conf,
                "knowledge_gap": True,
                "llm_error": result.get("error") or result.get("finish_reason"),
            }

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": list({c["source"] for c in chunks}),
            "avg_confidence": avg_conf,
            "best_confidence": best_conf,
            "knowledge_gap": False,
        }

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        words = text.split()
        return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size) if words[i:i + chunk_size]]


support_rag_service = SupportRAGService()

