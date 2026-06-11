"""
Módulo RAG para Ingenieros de Soporte.
Pipeline: Google Drive → Embeddings → ChromaDB → Gemini Pro
"""

import chromadb
from typing import Optional, Dict, List
import uuid

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service
from app.services.vertex.embeddings_service import embeddings_service
from app.services.gdrive_service import gdrive_service

SUPPORT_SYSTEM_PROMPT = """
Eres BOTIQ en modo Ingeniero de Soporte.
Tienes acceso a la base de conocimiento técnica de la empresa.

Tu función es:
1. Responder consultas técnicas usando la base de conocimiento disponible
2. Citar los documentos fuente cuando sea posible
3. Si no encuentras respuesta en la base de conocimiento, indicarlo claramente
4. Proporcionar pasos detallados para resolver problemas técnicos
5. Usar terminología técnica apropiada

Contexto de la base de conocimiento:
{knowledge_context}

Responde siempre en español y de forma estructurada con pasos claros cuando sea necesario.
"""


class SupportRAGService:
    """
    Servicio RAG para la base de conocimiento del ingeniero de soporte.
    """

    def __init__(self):
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self._chroma_client = None
        self._collection = None

    def _get_chroma_client(self):
        if self._chroma_client is None:
            self._chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
        return self._chroma_client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_chroma_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def sync_knowledge_base(self) -> Dict:
        """
        Sincroniza la base de conocimiento desde Google Drive.
        Descarga documentos, genera embeddings y los almacena en ChromaDB.
        """
        documents = await gdrive_service.get_all_documents_content()
        collection = self._get_collection()

        added = 0
        errors = 0

        for doc in documents:
            try:
                # Dividir documento en chunks de ~500 palabras
                chunks = self._chunk_text(doc["content"], chunk_size=500)

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
                            "chunk_index": i,
                            "modified_at": doc.get("modified_at", ""),
                        }],
                    )
                added += 1
            except Exception as e:
                print(f"Error procesando {doc['name']}: {e}")
                errors += 1

        return {
            "documents_processed": len(documents),
            "documents_added": added,
            "errors": errors,
        }

    async def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Recupera los chunks más relevantes para una consulta.
        """
        collection = self._get_collection()
        query_embedding = await embeddings_service.embed_text(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        context_chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                context_chunks.append({
                    "content": doc,
                    "source": meta.get("file_name", "Desconocido"),
                    "relevance_score": 1 - dist,  # Convertir distancia a similitud
                })

        return context_chunks

    async def generate_response(
        self,
        user_message: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Genera respuesta usando RAG + Gemini Pro.
        """
        # Enriquecer la query con el análisis de imagen si existe
        augmented_query = user_message
        if image_analysis:
            augmented_query = f"{user_message}\nContexto visual: {image_analysis}"

        # Recuperar contexto relevante
        context_chunks = await self.retrieve_context(augmented_query)

        # Construir contexto para el prompt
        if context_chunks:
            knowledge_context = "\n\n---\n\n".join([
                f"Fuente: {chunk['source']}\n{chunk['content']}"
                for chunk in context_chunks
            ])
        else:
            knowledge_context = "No se encontró información específica en la base de conocimiento."

        system_prompt = SUPPORT_SYSTEM_PROMPT.format(knowledge_context=knowledge_context)

        result = await gemini_text_service.generate(
            prompt=augmented_query,
            system_instruction=system_prompt,
            history=history,
            temperature=0.2,
        )

        sources = list(set([chunk["source"] for chunk in context_chunks]))
        avg_confidence = (
            sum(c["relevance_score"] for c in context_chunks) / len(context_chunks)
            if context_chunks else 0
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": sources,
            "context_chunks_used": len(context_chunks),
            "avg_confidence": avg_confidence,
        }

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Divide texto en chunks de tamaño aproximado por palabras."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks


support_rag_service = SupportRAGService()
