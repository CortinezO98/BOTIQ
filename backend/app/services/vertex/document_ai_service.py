"""Document AI service para extracción de texto en PDFs."""
import base64
from typing import Optional
from app.core.config import settings


class DocumentAIService:

    async def process_pdf(self, pdf_bytes: bytes) -> str:
        if not settings.DOCUMENT_AI_PROCESSOR_ID:
            return ""
        try:
            from google.cloud import documentai
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            opts = {"api_endpoint": f"{settings.DOCUMENT_AI_LOCATION}-documentai.googleapis.com"}
            client = documentai.DocumentProcessorServiceClient(credentials=creds, client_options=opts)
            processor_name = client.processor_path(
                settings.GCP_PROJECT_ID, settings.DOCUMENT_AI_LOCATION, settings.DOCUMENT_AI_PROCESSOR_ID
            )
            result = client.process_document(request=documentai.ProcessRequest(
                name=processor_name,
                raw_document=documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf"),
            ))
            return result.document.text
        except Exception as e:
            print(f"Document AI error: {e}")
            return ""

    async def process_pdf_base64(self, pdf_base64: str) -> str:
        return await self.process_pdf(base64.b64decode(pdf_base64))


document_ai_service = DocumentAIService()
