import asyncio, hashlib, random
from typing import List
from app.services.vertex.vertex_client import is_vertex_available
from app.core.config import settings


class EmbeddingsService:

    async def embed_text(self, text: str) -> List[float]:
        if not is_vertex_available():
            h = int(hashlib.md5(text.encode()).hexdigest(), 16)
            rng = random.Random(h)
            return [rng.gauss(0, 1) for _ in range(384)]
        from vertexai.language_models import TextEmbeddingModel
        model = TextEmbeddingModel.from_pretrained(settings.VERTEX_EMBEDDING_MODEL)
        loop = asyncio.get_event_loop()
        embs = await loop.run_in_executor(None, lambda: model.get_embeddings([text]))
        return embs[0].values

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            results.append(await self.embed_text(t))
        return results


embeddings_service = EmbeddingsService()


