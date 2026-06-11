"""Google Drive service para sincronización del RAG."""
import io
from typing import List, Dict, Optional
from app.core.config import settings


class GoogleDriveService:

    SUPPORTED_TYPES = {
        "application/vnd.google-apps.document": "text/plain",
        "application/pdf": "application/pdf",
        "text/plain": "text/plain",
    }

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    async def list_documents(self) -> List[Dict]:
        if not settings.GDRIVE_FOLDER_ID or not settings.GOOGLE_APPLICATION_CREDENTIALS:
            return []
        try:
            service = self._get_service()
            results = service.files().list(
                q=f"'{settings.GDRIVE_FOLDER_ID}' in parents and trashed=false",
                fields="files(id, name, mimeType, modifiedTime)",
                pageSize=100,
            ).execute()
            return [f for f in results.get("files", []) if f.get("mimeType") in self.SUPPORTED_TYPES]
        except Exception as e:
            print(f"GDrive error: {e}")
            return []

    async def download_document(self, file_id: str, mime_type: str) -> Optional[str]:
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
            return buffer.getvalue().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"Error descargando {file_id}: {e}")
            return None

    async def get_all_documents_content(self) -> List[Dict]:
        docs = await self.list_documents()
        result = []
        for doc in docs:
            content = await self.download_document(doc["id"], doc["mimeType"])
            if content:
                result.append({"file_id": doc["id"], "name": doc["name"], "content": content})
        return result


gdrive_service = GoogleDriveService()
