"""
Google Drive Service — BOTIQ RAG
═══════════════════════════════════════════════════════════

CÓMO CONECTAR GOOGLE DRIVE AL PROYECTO:
────────────────────────────────────────
PASO 1: Crear Service Account en Google Cloud
  - console.cloud.google.com → IAM y administración → Cuentas de servicio
  - "Crear cuenta de servicio" → Nombre: botiq-backend
  - No es necesario asignar roles del proyecto para solo leer Drive.
  - Entra a la cuenta creada → pestaña "Claves" → "Agregar clave" → "Crear clave nueva" → JSON
  - Guarda el archivo descargado como: backend/credentials/service-account.json

PASO 2: Habilitar las APIs en Google Cloud
  - APIs y servicios → Biblioteca → habilitar:
      • Google Drive API
      • Vertex AI API
      • (Opcional, PDFs escaneados) Document AI API

PASO 3: Compartir la carpeta de Drive con el Service Account
  - Abre la carpeta "Bot Soporte" en Drive
  - Compartir → agrega el email del Service Account
    (ej: botiq-backend@TU_PROYECTO.iam.gserviceaccount.com)
  - Permiso: Lector. Compartir.
  - IMPORTANTE: comparte la carpeta PADRE; las subcarpetas se heredan
    y este servicio las recorre de forma recursiva.

PASO 4: Obtener el ID de la carpeta
  - URL: drive.google.com/drive/folders/ESTE_ES_EL_ID
  - Pega ese ID en GDRIVE_FOLDER_ID del .env

PASO 5: Sincronizar
  - POST /api/v1/support/sync-knowledge-base (rol support_engineer o admin)

TIPOS DE ARCHIVO SOPORTADOS:
  ✅ Google Docs        → exportado como texto plano
  ✅ Google Sheets      → exportado como CSV
  ✅ .txt / .csv        → texto directo
  ✅ .xlsx / .xls       → todas las hojas extraídas como texto (openpyxl)
  ✅ .pdf digital       → extracción automática
  ✅ .pdf escaneado     → requiere Document AI (DOCUMENT_AI_PROCESSOR_ID)
  ⚠️ .docx              → soporte básico (texto plano)
═══════════════════════════════════════════════════════════
"""

import io
from typing import Dict, List, Optional

from app.core.config import settings

FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDriveService:

    # mime de Drive -> tipo lógico interno
    SUPPORTED_MIME_TYPES = {
        "application/vnd.google-apps.document": "google_doc",
        "application/vnd.google-apps.spreadsheet": "google_sheet",
        "application/pdf": "pdf",
        "text/plain": "text",
        "text/csv": "text",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",  # .xlsx
        "application/vnd.ms-excel": "xlsx",  # .xls antiguo
    }

    def __init__(self):
        self._service = None

    def _get_service(self):
        """Construye el cliente de Google Drive usando Service Account."""
        if self._service is None:
            import os

            if not settings.get_gdrive_folder_ids():
                raise RuntimeError("No hay carpetas configuradas (GDRIVE_FOLDER_ID / GDRIVE_FOLDER_IDS) en .env")
            if not settings.GOOGLE_APPLICATION_CREDENTIALS:
                raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS no configurado en .env")
            if not os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                raise RuntimeError(
                    f"Archivo de credenciales no encontrado: {settings.GOOGLE_APPLICATION_CREDENTIALS}\n"
                    f"Coloca el service-account.json en backend/credentials/"
                )
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _list_folder_raw(self, folder_id: str) -> List[Dict]:
        """Lista todos los hijos directos de una carpeta (con paginación)."""
        service = self._get_service()
        files: List[Dict] = []
        page_token = None
        query = f"'{folder_id}' in parents and trashed=false"
        while True:
            result = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    pageSize=100,
                    orderBy="modifiedTime desc",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return files

    async def list_documents(self) -> List[Dict]:
        """
        Lista todos los archivos soportados, recorriendo de forma recursiva
        cada carpeta raíz configurada (GDRIVE_FOLDER_ID + GDRIVE_FOLDER_IDS).
        Deduplica carpetas y archivos para que el solapamiento entre una raíz
        y sus subcarpetas no genere indexación doble.
        """
        roots = settings.get_gdrive_folder_ids()
        if not roots:
            print("⚠️  No hay carpetas configuradas (GDRIVE_FOLDER_ID / GDRIVE_FOLDER_IDS) — RAG sin documentos")
            return []
        try:
            supported: List[Dict] = []
            seen_files = set()        # file_id ya agregados
            visited = set()           # carpetas ya recorridas
            # Recorrido por amplitud sobre todas las raíces (evita recursión profunda).
            pending = list(roots)

            while pending:
                folder_id = pending.pop(0)
                if folder_id in visited:
                    continue
                visited.add(folder_id)

                for f in self._list_folder_raw(folder_id):
                    mime = f.get("mimeType")
                    if mime == FOLDER_MIME:
                        pending.append(f["id"])
                    elif mime in self.SUPPORTED_MIME_TYPES and f["id"] not in seen_files:
                        seen_files.add(f["id"])
                        supported.append(f)

            print(
                f"📁 Google Drive: {len(supported)} documentos soportados "
                f"en {len(visited)} carpeta(s), a partir de {len(roots)} raíz(es)"
            )
            return supported
        except Exception as e:  # noqa: BLE001
            print(f"❌ Google Drive error al listar: {e}")
            return []

    async def download_bytes(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """Descarga (o exporta) un archivo como bytes."""
        try:
            from googleapiclient.http import MediaIoBaseDownload

            service = self._get_service()

            if mime_type == "application/vnd.google-apps.document":
                request = service.files().export_media(fileId=file_id, mimeType="text/plain")
            elif mime_type == "application/vnd.google-apps.spreadsheet":
                # Google Sheets nativo → exportar como CSV (primera hoja).
                request = service.files().export_media(fileId=file_id, mimeType="text/csv")
            else:
                request = service.files().get_media(fileId=file_id, supportsAllDrives=True)

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()
        except Exception as e:  # noqa: BLE001
            print(f"❌ Error descargando {file_id}: {e}")
            return None

    @staticmethod
    def _xlsx_to_text(file_bytes: bytes) -> str:
        """Convierte un .xlsx/.xls en texto plano legible (todas las hojas)."""
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            blocks: List[str] = []
            for sheet in wb.worksheets:
                rows_text: List[str] = []
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        rows_text.append(" | ".join(cells))
                if rows_text:
                    blocks.append(f"[Hoja: {sheet.title}]\n" + "\n".join(rows_text))
            wb.close()
            return "\n\n".join(blocks)
        except Exception as e:  # noqa: BLE001
            print(f"❌ Error leyendo Excel: {e}")
            return ""

    async def get_all_documents_content_with_type(self) -> List[Dict]:
        """
        Descarga todos los documentos con metadata completa.
        - PDF: retorna bytes para Document AI.
        - XLSX/XLS: convierte a texto con openpyxl.
        - Resto: texto decodificado.
        """
        docs = await self.list_documents()
        result: List[Dict] = []

        for doc in docs:
            mime = doc["mimeType"]
            doc_type = self.SUPPORTED_MIME_TYPES.get(mime, "unknown")
            file_bytes = await self.download_bytes(doc["id"], mime)
            if not file_bytes:
                continue

            entry = {
                "file_id": doc["id"],
                "name": doc["name"],
                "mime_type": mime,
                "modified_at": doc.get("modifiedTime", ""),
                "doc_type": doc_type,
                "bytes": None,
                "content": "",
            }

            if mime == "application/pdf":
                # Se procesa con Document AI aguas arriba.
                entry["bytes"] = file_bytes
            elif doc_type == "xlsx":
                entry["content"] = self._xlsx_to_text(file_bytes)
            else:
                entry["content"] = file_bytes.decode("utf-8", errors="ignore")

            result.append(entry)

        return result

    async def get_all_documents_content(self) -> List[Dict]:
        """Compatibilidad con código anterior (solo entradas con texto)."""
        docs = await self.get_all_documents_content_with_type()
        return [d for d in docs if d.get("content")]

    def is_configured(self) -> bool:
        """Verifica si Google Drive está configurado."""
        import os

        return bool(
            settings.get_gdrive_folder_ids()
            and settings.GOOGLE_APPLICATION_CREDENTIALS
            and os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)
        )


gdrive_service = GoogleDriveService()
