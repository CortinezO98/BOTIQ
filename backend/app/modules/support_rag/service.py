from typing import Dict, List, Optional

from app.core.config import settings
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

    async def sync_knowledge_base(self) -> Dict:
        from app.services.vertex.document_ai_service import document_ai_service

        if not gdrive_service.is_configured():
            return {
                "status": "error",
                "message": "Google Drive no configurado. Verifica GDRIVE_FOLDER_ID y service-account.json",
                "documents_processed": 0,
            }

        documents = await gdrive_service.get_all_documents_content_with_type()
        if not documents:
            return {
                "status": "empty",
                "message": "No se encontraron documentos en la carpeta de Google Drive",
                "documents_processed": 0,
            }

        collection = self._get_collection()
        added, errors = 0, 0

        for doc in documents:
            try:
                if doc.get("doc_type") == "pdf" and doc.get("bytes"):
                    text = await document_ai_service.process_pdf(doc["bytes"])
                    if not text:
                        text = doc.get("content", "")
                else:
                    text = doc.get("content", "")

                if not text.strip():
                    print(f"⚠️  {doc['name']}: sin contenido extraíble")
                    continue

                chunks = self._chunk_text(text)
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

                print(f"✅ {doc['name']}: {len(chunks)} chunks indexados")
                added += 1
            except Exception as exc:
                print(f"❌ Error procesando {doc.get('name')}: {exc}")
                errors += 1

        return {
            "status": "success",
            "documents_processed": len(documents),
            "documents_added": added,
            "errors": errors,
            "total_chunks": self._get_collection().count(),
        }

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
        except Exception as exc:
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

        if not chunks or avg_conf < settings.RAG_MIN_CONFIDENCE:
            return {
                "text": NO_KNOWLEDGE,
                "sources": [],
                "avg_confidence": avg_conf,
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
            model=settings.VERTEX_REASONING_MODEL,
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": list({c["source"] for c in chunks}),
            "avg_confidence": avg_conf,
            "knowledge_gap": False,
        }

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        words = text.split()
        return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size) if words[i:i + chunk_size]]


support_rag_service = SupportRAGService()
