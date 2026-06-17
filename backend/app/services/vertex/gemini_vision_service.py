import base64, time
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
            img = Part.from_data(data=base64.b64decode(image_base64), mime_type=mime_type)
            prompt = """Analiza esta captura y proporciona en español:
1. Descripción general
2. Texto visible
3. Errores detectados
4. Solución recomendada"""
            resp = await model.generate_content_async(
                [img, prompt],
                generation_config=GenerationConfig(temperature=0.1, max_output_tokens=1024)
            )
            return {"description": resp.text, "tokens_used": getattr(resp.usage_metadata, "total_token_count", None)}
        except Exception as e:
            return {"description": f"Error analizando imagen: {e}", "ocr_text": ""}


gemini_vision_service = GeminiVisionService()


