"""
Servicio de sincronización con Google Drive.
Lee documentos de la carpeta configurada para alimentar el RAG.
"""

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import io
import os
from typing import List, Dict, Optional
from datetime import datetime

from app.core.config import settings


class GoogleDriveService:
    """
    Gestiona la lectura de documentos desde Google Drive.
    La carpeta configurada contiene la base de conocimiento del RAG.
    """

    SUPPORTED_TYPES = {
        "application/vnd.google-apps.document": "text/plain",
        "application/pdf": "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "text/plain",
        "text/plain": "text/plain",
    }

    def __init__(self):
        self.folder_id = settings.GDRIVE_FOLDER_ID
        self._service = None

    def _get_service(self):
        if self._service is None:
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    async def list_documents(self) -> List[Dict]:
        """
        Lista todos los documentos en la carpeta configurada.
        """
        service = self._get_service()
        query = f"'{self.folder_id}' in parents and trashed=false"

        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime, size)",
            pageSize=100,
        ).execute()

        files = results.get("files", [])
        return [f for f in files if f.get("mimeType") in self.SUPPORTED_TYPES]

    async def download_document(self, file_id: str, mime_type: str) -> Optional[str]:
        """
        Descarga el contenido de un documento como texto.
        """
        service = self._get_service()

        try:
            if mime_type == "application/vnd.google-apps.document":
                # Google Docs → exportar como texto plano
                request = service.files().export_media(
                    fileId=file_id, mimeType="text/plain"
                )
            else:
                # Otros archivos → descargar directamente
                request = service.files().get_media(fileId=file_id)

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            content = buffer.getvalue().decode("utf-8", errors="ignore")
            return content

        except Exception as e:
            print(f"Error descargando {file_id}: {e}")
            return None

    async def get_all_documents_content(self) -> List[Dict]:
        """
        Obtiene el contenido de todos los documentos de la carpeta.
        Retorna lista de dicts con 'name', 'content', 'file_id'.
        """
        documents = await self.list_documents()
        result = []

        for doc in documents:
            content = await self.download_document(doc["id"], doc["mimeType"])
            if content:
                result.append({
                    "file_id": doc["id"],
                    "name": doc["name"],
                    "content": content,
                    "modified_at": doc.get("modifiedTime"),
                })

        return result


gdrive_service = GoogleDriveService()
