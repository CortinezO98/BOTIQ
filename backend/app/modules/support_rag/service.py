"""Módulo RAG para Ingenieros de Soporte."""
from typing import Optional, Dict, List
from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service
from app.services.vertex.embeddings_service import embeddings_service
from app.services.gdrive_service import gdrive_service

SYSTEM_PROMPT = """Eres BOTIQ en modo Ingeniero de Soporte.
Tienes acceso a la base de conocimiento técnica de la empresa.

Contexto recuperado:
{knowledge_context}

Instrucciones:
1. Responde usando el contexto anterior como base
2. Cita las fuentes cuando sea posible
3. Si no encuentras información, indícalo claramente
4. Proporciona pasos detallados para resolver problemas
5. Responde en español
"""


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
        documents = await gdrive_service.get_all_documents_content()
        if not documents:
            return {"documents_processed": 0, "message": "No hay documentos en Google Drive o no está configurado"}

        collection = self._get_collection()
        added, errors = 0, 0

        for doc in documents:
            try:
                chunks = self._chunk_text(doc["content"])
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{doc['file_id']}_chunk_{i}"
                    embedding = await embeddings_service.embed_text(chunk)
                    collection.upsert(
                        ids=[chunk_id],
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{"file_name": doc["name"], "chunk_index": i}],
                    )
                added += 1
            except Exception as e:
                print(f"Error procesando {doc.get('name')}: {e}")
                errors += 1

        return {"documents_processed": len(documents), "documents_added": added, "errors": errors}

    async def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict]:
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []
            query_embedding = await embeddings_service.embed_text(query)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
            chunks = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                    chunks.append({"content": doc, "source": meta.get("file_name", "Desconocido"), "relevance_score": 1 - dist})
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
        augmented = f"{user_message}\nContexto visual: {image_analysis}" if image_analysis else user_message
        context_chunks = await self.retrieve_context(augmented)

        if context_chunks:
            knowledge_context = "\n\n---\n\n".join([f"Fuente: {c['source']}\n{c['content']}" for c in context_chunks])
        else:
            knowledge_context = "No se encontró información específica en la base de conocimiento."

        result = await gemini_text_service.generate(
            prompt=augmented,
            system_instruction=SYSTEM_PROMPT.format(knowledge_context=knowledge_context),
            history=history,
            temperature=0.2,
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": list(set(c["source"] for c in context_chunks)),
        }

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        words = text.split()
        return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size) if words[i:i+chunk_size]]


support_rag_service = SupportRAGService()
