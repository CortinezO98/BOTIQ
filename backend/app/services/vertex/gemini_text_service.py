"""
Servicio de generación de texto con Gemini Pro via Vertex AI.
"""

from vertexai.generative_models import GenerativeModel, GenerationConfig
from typing import Optional, List, Dict
import time

from app.core.config import settings
from app.services.vertex.vertex_client import init_vertex_ai


class GeminiTextService:
    """
    Wrapper sobre Gemini Pro para generación de texto conversacional.
    """

    def __init__(self):
        self.model_name = settings.VERTEX_GEMINI_MODEL
        self._model: Optional[GenerativeModel] = None

    def _get_model(self) -> GenerativeModel:
        if self._model is None:
            self._model = GenerativeModel(self.model_name)
        return self._model

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 1024,
    ) -> Dict:
        """
        Genera una respuesta de texto con Gemini.

        Returns:
            dict con 'text', 'tokens_used', 'response_time_ms'
        """
        start_time = time.time()

        model = GenerativeModel(
            self.model_name,
            system_instruction=system_instruction,
        )

        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Construir historial de conversación si existe
        chat_history = []
        if history:
            for msg in history:
                chat_history.append({
                    "role": msg["role"],
                    "parts": [{"text": msg["content"]}],
                })

        chat = model.start_chat(history=chat_history)
        response = await chat.send_message_async(
            prompt,
            generation_config=generation_config,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "text": response.text,
            "tokens_used": response.usage_metadata.total_token_count if response.usage_metadata else None,
            "response_time_ms": elapsed_ms,
        }


gemini_text_service = GeminiTextService()
