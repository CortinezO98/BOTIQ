"""
Módulo RAG para Ingenieros de Soporte.
MEJORAS:
  - Umbral de confianza mínima (RAG_MIN_CONFIDENCE)
  - Detecta knowledge_gap cuando la confianza es baja
  - Integra Document AI para PDFs reales
  - Metadata enriquecida por chunk
"""
from typing import Optional, Dict, List
from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service
from app.services.vertex.embeddings_service import embeddings_service
from app.services.gdrive_service import gdrive_service

RAG_MIN_CONFIDENCE: float = 0.72  # Umbral mínimo — si no se alcanza, es knowledge_gap

SYSTEM_PROMPT = """Eres BOTIQ en modo Ingeniero de Soporte.
Tienes acceso a la base de conocimiento técnica de la empresa.

CONTEXTO RECUPERADO:
{knowledge_context}

INSTRUCCIONES:
1. Responde usando ÚNICAMENTE el contexto anterior como base
2. Cita las fuentes entre paréntesis al final de cada afirmación relevante
3. Si el contexto no es suficiente, dilo explícitamente
4. Proporciona pasos numerados para resolver problemas técnicos
5. Responde en español con terminología técnica apropiada
6. NUNCA inventes procedimientos que no estén en el contexto
"""

NO_KNOWLEDGE_RESPONSE = (
    "No encontré información suficiente en la base de conocimiento para darte "
    "una respuesta confiable sobre este tema. "
    "Te recomiendo:\n"
    "1. Documentar este caso para enriquecer la base de conocimiento\n"
    "2. Escalarlo a un especialista\n"
    "3. Consultar la documentación oficial del proveedor"
)


class SupportRAGService:

    def __init__(self):
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def sync_knowledge_base(self) -> Dict:
        """
        Sincroniza desde Google Drive.
        - Google Docs / TXT → texto directo
        - PDFs → Document AI para extracción precisa
        """
        from app.services.vertex.document_ai_service import document_ai_service

        documents = await gdrive_service.get_all_documents_content_with_type()
        if not documents:
            return {
                "documents_processed": 0,
                "message": "Google Drive no configurado o carpeta vacía",
            }

        collection = self._get_collection()
        added, errors = 0, 0

        for doc in documents:
            try:
                # Si es PDF → usar Document AI para extracción real
                if doc.get("mime_type") == "application/pdf" and doc.get("bytes"):
                    text = await document_ai_service.process_pdf(doc["bytes"])
                    if not text:
                        # Fallback al texto básico si Document AI no está configurado
                        text = doc.get("content", "")
                else:
                    text = doc.get("content", "")

                if not text.strip():
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
                            "mime_type": doc.get("mime_type", ""),
                            "modified_at": doc.get("modified_at", ""),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "content_hash": str(hash(chunk)),
                        }],
                    )
                added += 1
            except Exception as e:
                print(f"Error procesando {doc.get('name')}: {e}")
                errors += 1

        return {
            "documents_processed": len(documents),
            "documents_added": added,
            "errors": errors,
        }

    async def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict]:
        """Recupera chunks más relevantes con score de confianza."""
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []

            query_embedding = await embeddings_service.embed_text(query)
            n = min(top_k, collection.count())

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    relevance = max(0.0, 1 - dist)
                    chunks.append({
                        "content": doc,
                        "source": meta.get("file_name", "Desconocido"),
                        "file_id": meta.get("file_id", ""),
                        "relevance_score": relevance,
                        "chunk_index": meta.get("chunk_index", 0),
                    })

            # Ordenar por relevancia descendente
            chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
            return chunks

        except Exception as e:
            print(f"ChromaDB retrieve error: {e}")
            return []

    async def generate_response(
        self,
        user_message: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Genera respuesta con RAG.
        Si la confianza es < RAG_MIN_CONFIDENCE → retorna knowledge_gap=True
        """
        augmented = (
            f"{user_message}\nContexto visual: {image_analysis}"
            if image_analysis else user_message
        )

        context_chunks = await self.retrieve_context(augmented)

        # Calcular confianza promedio de los chunks recuperados
        avg_confidence = 0.0
        if context_chunks:
            avg_confidence = sum(c["relevance_score"] for c in context_chunks) / len(context_chunks)

        # ── Umbral de confianza ──────────────────────────────────────────────
        if not context_chunks or avg_confidence < RAG_MIN_CONFIDENCE:
            return {
                "text": NO_KNOWLEDGE_RESPONSE,
                "sources": [],
                "avg_confidence": avg_confidence,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
            }

        # Construir contexto para el prompt
        knowledge_context = "\n\n---\n\n".join([
            f"[Fuente: {c['source']}]\n{c['content']}"
            for c in context_chunks
        ])

        result = await gemini_text_service.generate(
            prompt=augmented,
            system_instruction=SYSTEM_PROMPT.format(knowledge_context=knowledge_context),
            history=history,
            temperature=0.2,
        )

        sources = list({c["source"] for c in context_chunks})

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": sources,
            "avg_confidence": avg_confidence,
            "context_chunks_used": len(context_chunks),
            "knowledge_gap": False,
        }

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Chunking semántico básico por palabras."""
        words = text.split()
        return [
            " ".join(words[i:i + chunk_size])
            for i in range(0, len(words), chunk_size)
            if words[i:i + chunk_size]
        ]


support_rag_service = SupportRAGService()
