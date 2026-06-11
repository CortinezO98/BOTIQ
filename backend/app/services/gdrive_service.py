"""
Google Drive service — con soporte real de PDFs via Document AI.
"""
import io
from typing import List, Dict, Optional
from app.core.config import settings


class GoogleDriveService:

    SUPPORTED_TYPES = {
        "application/vnd.google-apps.document": "text/plain",
        "application/pdf": "application/pdf",
        "text/plain": "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "text/plain",
    }

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
            import os
            if not settings.GOOGLE_APPLICATION_CREDENTIALS or \
               not os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS no configurado")
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    async def list_documents(self) -> List[Dict]:
        if not settings.GDRIVE_FOLDER_ID:
            return []
        try:
            service = self._get_service()
            results = service.files().list(
                q=f"'{settings.GDRIVE_FOLDER_ID}' in parents and trashed=false",
                fields="files(id, name, mimeType, modifiedTime, size)",
                pageSize=100,
            ).execute()
            return [
                f for f in results.get("files", [])
                if f.get("mimeType") in self.SUPPORTED_TYPES
            ]
        except Exception as e:
            print(f"GDrive list error: {e}")
            return []

    async def download_document_bytes(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """Descarga el archivo como bytes (para PDFs → Document AI)."""
        try:
            from googleapiclient.http import MediaIoBaseDownload
            service = self._get_service()

            if mime_type == "application/vnd.google-apps.document":
                request = service.files().export_media(fileId=file_id, mimeType="text/plain")
            else:
                request = service.files().get_media(fileId=file_id)

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()
        except Exception as e:
            print(f"GDrive download error ({file_id}): {e}")
            return None

    async def get_all_documents_content_with_type(self) -> List[Dict]:
        """
        Retorna documentos con su contenido y tipo MIME.
        PDFs retornan también los bytes para Document AI.
        """
        docs = await self.list_documents()
        result = []

        for doc in docs:
            mime = doc["mimeType"]
            file_bytes = await self.download_document_bytes(doc["id"], mime)
            if not file_bytes:
                continue

            entry = {
                "file_id": doc["id"],
                "name": doc["name"],
                "mime_type": mime,
                "modified_at": doc.get("modifiedTime", ""),
            }

            if mime == "application/pdf":
                # Para PDFs → pasar bytes a Document AI en el servicio RAG
                entry["bytes"] = file_bytes
                entry["content"] = ""  # Se llenará con Document AI
            else:
                # Para texto/Google Docs → decodificar directamente
                entry["content"] = file_bytes.decode("utf-8", errors="ignore")
                entry["bytes"] = None

            result.append(entry)

        return result

    # Compatibilidad con código anterior
    async def get_all_documents_content(self) -> List[Dict]:
        docs = await self.get_all_documents_content_with_type()
        return [d for d in docs if d.get("content")]


gdrive_service = GoogleDriveService()
