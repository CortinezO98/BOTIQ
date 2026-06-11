"""
Servicio Gemini Pro para generación de texto via Vertex AI.
Incluye fallback para modo demo (sin credenciales GCP).
"""

import time
from typing import Optional, List, Dict

from app.services.vertex.vertex_client import init_vertex_ai, is_vertex_available
from app.core.config import settings

# Intentar inicializar al importar
init_vertex_ai()

FALLBACK_RESPONSE = (
    "Estoy en modo demo. Para habilitar respuestas reales con IA, "
    "configura las credenciales de Google Cloud (Vertex AI) en el archivo .env."
)


class GeminiTextService:

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_output_tokens: int = 1024,
    ) -> Dict:
        start_time = time.time()

        if not is_vertex_available():
            return {
                "text": FALLBACK_RESPONSE,
                "tokens_used": 0,
                "response_time_ms": (time.time() - start_time) * 1000,
            }

        try:
            from vertexai.generative_models import GenerativeModel, GenerationConfig

            model = GenerativeModel(
                settings.VERTEX_GEMINI_MODEL,
                system_instruction=system_instruction,
            )
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

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

            return {
                "text": response.text,
                "tokens_used": getattr(response.usage_metadata, "total_token_count", None),
                "response_time_ms": (time.time() - start_time) * 1000,
            }

        except Exception as e:
            print(f"Error Gemini: {e}")
            return {
                "text": f"Error al procesar con IA: {str(e)}. Verifica la configuración de Vertex AI.",
                "tokens_used": 0,
                "response_time_ms": (time.time() - start_time) * 1000,
            }


gemini_text_service = GeminiTextService()
