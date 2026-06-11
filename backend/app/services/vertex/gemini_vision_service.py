"""Servicio Gemini Vision para análisis de imágenes."""
import base64
import time
from typing import Dict

from app.services.vertex.vertex_client import is_vertex_available
from app.core.config import settings


class GeminiVisionService:

    async def analyze_error_screenshot(self, image_base64: str, mime_type: str = "image/jpeg") -> Dict:
        if not is_vertex_available():
            return {"description": "Análisis de imagen no disponible en modo demo.", "ocr_text": ""}

        try:
            from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

            model = GenerativeModel(settings.VERTEX_VISION_MODEL)
            image_bytes = base64.b64decode(image_base64)
            image_part = Part.from_data(data=image_bytes, mime_type=mime_type)

            prompt = """Analiza esta captura de pantalla y proporciona:
1. Descripción general de lo que muestra
2. Texto visible en la imagen
3. Errores o problemas detectados
4. Solución recomendada si hay un error

Responde en español."""

            response = await model.generate_content_async(
                [image_part, prompt],
                generation_config=GenerationConfig(temperature=0.1, max_output_tokens=1024),
            )
            return {
                "description": response.text,
                "tokens_used": getattr(response.usage_metadata, "total_token_count", None),
            }
        except Exception as e:
            return {"description": f"Error analizando imagen: {e}", "ocr_text": ""}


gemini_vision_service = GeminiVisionService()
