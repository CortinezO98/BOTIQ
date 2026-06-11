"""
Google Drive Service — BOTIQ RAG
═══════════════════════════════════════════════════════════

CÓMO CONECTAR GOOGLE DRIVE AL PROYECTO:
────────────────────────────────────────
PASO 1: Crear Service Account en Google Cloud
  - Ve a: console.cloud.google.com → IAM → Service Accounts
  - Clic "Crear cuenta de servicio"
  - Nombre: botiq-backend
  - Roles: Editor (o mínimo: roles/drive.readonly)
  - Descargar clave JSON → guardar en backend/credentials/service-account.json

PASO 2: Habilitar Google Drive API
  - Ve a: console.cloud.google.com → APIs y Servicios → Biblioteca
  - Buscar "Google Drive API" → Habilitar

PASO 3: Compartir la carpeta de Drive
  - Abre Google Drive en el navegador
  - Crea una carpeta: "BOTIQ - Base de Conocimiento"
  - Clic derecho → Compartir
  - Agrega el email del Service Account (ej: botiq-backend@proyecto.iam.gserviceaccount.com)
  - Permiso: Lector
  - Clic "Compartir"

PASO 4: Obtener el ID de la carpeta
  - Abre la carpeta en Drive
  - La URL es: drive.google.com/drive/folders/ESTE_ES_EL_ID
  - Copia ese ID y pégalo en GDRIVE_FOLDER_ID del .env

PASO 5: Sincronizar
  - POST /api/v1/support/sync-knowledge-base (requiere rol support_engineer o admin)
  - El bot procesará todos los documentos y los indexará en ChromaDB

TIPOS DE ARCHIVO SOPORTADOS:
  ✅ Google Docs (.gdoc) → se exporta como texto plano
  ✅ .txt → texto directo
  ✅ .pdf con texto digital → extracción automática
  ✅ .pdf escaneado → requiere Document AI (configurar DOCUMENT_AI_PROCESSOR_ID)
  ⚠️ .docx → soporte básico (texto plano)
═══════════════════════════════════════════════════════════
"""

import io
from typing import List, Dict, Optional
from app.core.config import settings


class GoogleDriveService:

    SUPPORTED_MIME_TYPES = {
        "application/vnd.google-apps.document": "google_doc",
        "application/pdf": "pdf",
        "text/plain": "text",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }

    def __init__(self):
        self._service = None

    def _get_service(self):
        """Construye el cliente de Google Drive usando Service Account."""
        if self._service is None:
            import os
            if not settings.GDRIVE_FOLDER_ID:
                raise RuntimeError("GDRIVE_FOLDER_ID no configurado en .env")
            if not settings.GOOGLE_APPLICATION_CREDENTIALS:
                raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS no configurado en .env")
            if not os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                raise RuntimeError(
                    f"Archivo de credenciales no encontrado: {settings.GOOGLE_APPLICATION_CREDENTIALS}\n"
                    f"Coloca el service-account.json en backend/credentials/"
                )
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    async def list_documents(self) -> List[Dict]:
        """Lista todos los archivos soportados en la carpeta configurada."""
        if not settings.GDRIVE_FOLDER_ID:
            print("⚠️  GDRIVE_FOLDER_ID no configurado — RAG sin documentos")
            return []
        try:
            service = self._get_service()
            query = f"'{settings.GDRIVE_FOLDER_ID}' in parents and trashed=false"
            result = service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime, size)",
                pageSize=100,
                orderBy="modifiedTime desc",
            ).execute()
            files = result.get("files", [])
            supported = [f for f in files if f.get("mimeType") in self.SUPPORTED_MIME_TYPES]
            print(f"📁 Google Drive: {len(supported)} documentos encontrados en carpeta {settings.GDRIVE_FOLDER_ID}")
            return supported
        except Exception as e:
            print(f"❌ Google Drive error al listar: {e}")
            return []

    async def download_bytes(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """Descarga un archivo como bytes."""
        try:
            from googleapiclient.http import MediaIoBaseDownload
            service = self._get_service()
            if mime_type == "application/vnd.google-apps.document":
                # Google Docs → exportar como texto plano
                request = service.files().export_media(fileId=file_id, mimeType="text/plain")
            else:
                # Resto → descargar directamente
                request = service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()
        except Exception as e:
            print(f"❌ Error descargando {file_id}: {e}")
            return None

    async def get_all_documents_content_with_type(self) -> List[Dict]:
        """
        Descarga todos los documentos con metadata completa.
        PDFs retornan bytes para Document AI.
        Resto retornan texto decodificado.
        """
        docs = await self.list_documents()
        result = []
        for doc in docs:
            mime = doc["mimeType"]
            file_bytes = await self.download_bytes(doc["id"], mime)
            if not file_bytes:
                continue
            entry = {
                "file_id": doc["id"],
                "name": doc["name"],
                "mime_type": mime,
                "modified_at": doc.get("modifiedTime", ""),
                "doc_type": self.SUPPORTED_MIME_TYPES.get(mime, "unknown"),
            }
            if mime == "application/pdf":
                entry["bytes"] = file_bytes
                entry["content"] = ""
            else:
                entry["content"] = file_bytes.decode("utf-8", errors="ignore")
                entry["bytes"] = None
            result.append(entry)
        return result

    async def get_all_documents_content(self) -> List[Dict]:
        """Compatibilidad con código anterior."""
        docs = await self.get_all_documents_content_with_type()
        return [d for d in docs if d.get("content")]

    def is_configured(self) -> bool:
        """Verifica si Google Drive está configurado."""
        import os
        return bool(
            settings.GDRIVE_FOLDER_ID and
            settings.GOOGLE_APPLICATION_CREDENTIALS and
            os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)
        )


gdrive_service = GoogleDriveService()
