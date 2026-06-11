"""
Servicio de Document AI de Google Cloud.
Extrae texto estructurado de PDFs y documentos escaneados para el RAG.
"""

import base64
from typing import Optional
from google.cloud import documentai
from google.oauth2 import service_account

from app.core.config import settings


class DocumentAIService:
    """
    Procesa documentos (PDFs, imágenes de documentos) para extraer
    texto estructurado con alta precisión usando Document AI.
    Complementa a Google Drive para documentos escaneados o complejos.
    """

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.DOCUMENT_AI_LOCATION
        self.processor_id = settings.DOCUMENT_AI_PROCESSOR_ID
        self._client: Optional[documentai.DocumentProcessorServiceClient] = None

    def _get_client(self) -> documentai.DocumentProcessorServiceClient:
        if self._client is None:
            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                opts = {"api_endpoint": f"{self.location}-documentai.googleapis.com"}
                self._client = documentai.DocumentProcessorServiceClient(
                    credentials=credentials,
                    client_options=opts,
                )
            else:
                opts = {"api_endpoint": f"{self.location}-documentai.googleapis.com"}
                self._client = documentai.DocumentProcessorServiceClient(client_options=opts)
        return self._client

    async def process_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extrae texto de un PDF usando Document AI.

        Args:
            pdf_bytes: Bytes del archivo PDF

        Returns:
            Texto extraído del documento
        """
        if not self.processor_id:
            # Fallback: retornar vacío si no está configurado
            print("⚠️ Document AI processor no configurado. Saltando procesamiento.")
            return ""

        client = self._get_client()
        processor_name = client.processor_path(
            self.project_id, self.location, self.processor_id
        )

        raw_document = documentai.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        )

        request = documentai.ProcessRequest(
            name=processor_name,
            raw_document=raw_document,
        )

        result = client.process_document(request=request)
        document = result.document

        return document.text

    async def process_pdf_base64(self, pdf_base64: str) -> str:
        """
        Extrae texto de un PDF en base64.
        """
        pdf_bytes = base64.b64decode(pdf_base64)
        return await self.process_pdf(pdf_bytes)


document_ai_service = DocumentAIService()
