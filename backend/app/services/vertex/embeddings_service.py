"""
Servicio de generación de embeddings con Vertex AI.
Usado en el pipeline RAG para el módulo de ingeniero de soporte.
"""

from vertexai.language_models import TextEmbeddingModel
from typing import List
import asyncio

from app.core.config import settings


class EmbeddingsService:
    """
    Genera embeddings de texto usando text-multilingual-embedding-002.
    Soporte multilenguaje, optimizado para español e inglés.
    """

    def __init__(self):
        self.model_name = settings.VERTEX_EMBEDDING_MODEL
        self._model: TextEmbeddingModel = None

    def _get_model(self) -> TextEmbeddingModel:
        if self._model is None:
            self._model = TextEmbeddingModel.from_pretrained(self.model_name)
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        """
        Genera embedding para un texto individual.
        """
        model = self._get_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.get_embeddings([text])
        )
        return embeddings[0].values

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos en batch.
        Más eficiente que llamadas individuales.
        """
        model = self._get_model()
        loop = asyncio.get_event_loop()

        # Vertex AI tiene límite de 250 textos por batch
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await loop.run_in_executor(
                None,
                lambda b=batch: model.get_embeddings(b)
            )
            all_embeddings.extend([e.values for e in embeddings])

        return all_embeddings


embeddings_service = EmbeddingsService()
