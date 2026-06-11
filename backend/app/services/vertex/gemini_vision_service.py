"""
Servicio de análisis de imágenes con Gemini Pro Vision via Vertex AI.
Integra también Cloud Vision API para OCR avanzado.
"""

import base64
import time
from typing import Optional, Dict
from vertexai.generative_models import GenerativeModel, Part, Image, GenerationConfig
from google.cloud import vision

from app.core.config import settings


class GeminiVisionService:
    """
    Analiza imágenes usando Gemini Pro Vision.
    Soporta capturas de error, diagramas, tableros de servidores.
    """

    def __init__(self):
        self.model_name = settings.VERTEX_VISION_MODEL
        self.vision_client = vision.ImageAnnotatorClient()

    async def analyze_image(
        self,
        image_base64: str,
        mime_type: str = "image/jpeg",
        context_prompt: str = "Describe detalladamente qué muestra esta imagen, especialmente si hay errores, mensajes del sistema o información técnica.",
    ) -> Dict:
        """
        Analiza una imagen con Gemini Vision.

        Args:
            image_base64: Imagen codificada en base64
            mime_type: Tipo MIME de la imagen
            context_prompt: Instrucción para el análisis

        Returns:
            dict con 'description', 'extracted_text', 'error_detected', 'tokens_used'
        """
        start_time = time.time()

        model = GenerativeModel(self.model_name)
        generation_config = GenerationConfig(temperature=0.1, max_output_tokens=1024)

        image_bytes = base64.b64decode(image_base64)
        image_part = Part.from_data(data=image_bytes, mime_type=mime_type)

        full_prompt = f"""
        {context_prompt}

        Analiza la imagen y proporciona:
        1. Descripción general de lo que muestra
        2. Texto visible en la imagen (si hay)
        3. Errores o problemas detectados (si hay)
        4. Contexto técnico relevante

        Responde en español de forma estructurada.
        """

        response = await model.generate_content_async(
            [image_part, full_prompt],
            generation_config=generation_config,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "description": response.text,
            "tokens_used": response.usage_metadata.total_token_count if response.usage_metadata else None,
            "response_time_ms": elapsed_ms,
        }

    async def extract_text_ocr(self, image_base64: str) -> str:
        """
        Extrae texto de una imagen usando Cloud Vision API (OCR).
        Útil para documentos escaneados o capturas con texto denso.
        """
        image_bytes = base64.b64decode(image_base64)
        image = vision.Image(content=image_bytes)

        response = self.vision_client.document_text_detection(image=image)
        texts = response.text_annotations

        if texts:
            return texts[0].description
        return ""

    async def analyze_error_screenshot(
        self,
        image_base64: str,
        mime_type: str = "image/jpeg",
    ) -> Dict:
        """
        Análisis especializado para capturas de error del sistema.
        Combina Gemini Vision + OCR para máxima precisión.
        """
        # Extraer texto con OCR primero
        extracted_text = await self.extract_text_ocr(image_base64)

        # Luego analizar contexto con Gemini Vision
        context_prompt = f"""
        Esta es una captura de pantalla de un error de sistema.
        Texto extraído por OCR: {extracted_text[:500] if extracted_text else 'No disponible'}

        Por favor identifica:
        - El tipo de error (sistema, aplicación, red, etc.)
        - El mensaje de error exacto
        - La aplicación o sistema afectado
        - Posibles causas
        - Solución recomendada
        """

        analysis = await self.analyze_image(image_base64, mime_type, context_prompt)
        analysis["ocr_text"] = extracted_text

        return analysis


gemini_vision_service = GeminiVisionService()
