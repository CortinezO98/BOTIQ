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
      • Google Sheets API (necesaria para leer pestañas específicas por gid)
      • Vertex AI API
      • (Opcional, PDFs escaneados) Document AI API

PASO 3: Compartir con el Service Account
  - Carpeta completa: Compartir → email del service account → Lector.
  - Archivo suelto (sin carpeta): igual, Compartir → email del service
    account → Lector, directo sobre el archivo.

PASO 4: Obtener el ID (y el gid, si aplica)
  - Carpeta:  drive.google.com/drive/folders/ESTE_ES_EL_ID
  - Archivo:  docs.google.com/spreadsheets/d/ESTE_ES_EL_ID/edit
  - Pestaña específica de un Sheet: .../edit?gid=ESTE_ES_EL_GID#gid=...
    (si la tabla que te interesa NO está en la primera pestaña, necesitas
    el gid -- de lo contrario el export trae la pestaña equivocada)

PASO 5: Sincronizar
  - Soporte:    POST /api/v1/support/sync-knowledge-base
  - Servidores: POST /api/v1/servers-kb/sync-knowledge-base

TIPOS DE ARCHIVO SOPORTADOS:
  ✅ Google Docs        → exportado como texto plano
  ✅ Google Sheets      → exportado como CSV (primera pestaña) o, si se
                          configura un gid, leído por Sheets API (pestaña exacta)
  ✅ .txt / .csv        → texto directo
  ✅ .xlsx / .xls       → todas las hojas extraídas como texto (openpyxl)
  ✅ .pdf digital       → extracción automática
  ✅ .pdf escaneado     → requiere Document AI (DOCUMENT_AI_PROCESSOR_ID)
  ⚠️ .docx              → soporte básico (texto plano)

NOTA: este servicio es genérico -- no está atado a una sola base de
conocimiento. Cada método acepta `folder_ids` y `file_ids` opcionales; si no
se pasan, usa por compatibilidad las carpetas de soporte
(settings.get_gdrive_folder_ids()).
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
        self._sheets_service = None

    def _get_service(self):
        """Construye el cliente de Google Drive usando Service Account."""
        if self._service is None:
            import os

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
                scopes=[
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/spreadsheets.readonly",
                ],
            )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
            self._sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._service

    def _get_sheets_service(self):
        if self._sheets_service is None:
            self._get_service()  # construye ambos clientes con las mismas credenciales
        return self._sheets_service

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

    def _get_file_raw(self, file_id: str) -> Optional[Dict]:
        """Obtiene metadata de un archivo suelto por su ID directo."""
        service = self._get_service()
        try:
            return (
                service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, mimeType, modifiedTime, size",
                    supportsAllDrives=True,
                )
                .execute()
            )
        except Exception as e:  # noqa: BLE001
            print(f"❌ Google Drive error al obtener archivo {file_id}: {e}")
            return None

    async def list_documents(
        self,
        folder_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Lista todos los archivos soportados:
        - Recorriendo de forma recursiva cada carpeta raíz en `folder_ids`.
        - Sumando cada archivo suelto listado explícitamente en `file_ids`.
        Si ninguno de los dos se pasa, usa por compatibilidad las carpetas de
        soporte configuradas (settings.get_gdrive_folder_ids()). Deduplica
        por file_id sin importar de qué fuente vino cada documento.
        """
        roots = folder_ids if folder_ids is not None else settings.get_gdrive_folder_ids()
        explicit_files = file_ids or []

        if not roots and not explicit_files:
            print("⚠️  No hay carpetas ni archivos configurados para esta base de conocimiento")
            return []

        try:
            supported: List[Dict] = []
            seen_files = set()        # file_id ya agregados
            visited = set()           # carpetas ya recorridas

            # 1) Carpetas, recorrido recursivo por amplitud.
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

            # 2) Archivos sueltos por ID directo (sin pasar por ninguna carpeta).
            for file_id in explicit_files:
                if file_id in seen_files:
                    continue  # ya vino por alguna carpeta -- evita duplicado
                meta = self._get_file_raw(file_id)
                if not meta:
                    continue
                mime = meta.get("mimeType")
                if mime in self.SUPPORTED_MIME_TYPES:
                    seen_files.add(file_id)
                    supported.append(meta)
                else:
                    print(f"⚠️  Archivo {file_id} ({meta.get('name')}) tiene un tipo no soportado: {mime}")

            print(
                f"📁 Google Drive: {len(supported)} documentos soportados "
                f"({len(visited)} carpeta(s) recorrida(s), {len(explicit_files)} archivo(s) directo(s))"
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
                # Google Sheets nativo → exportar como CSV (SIEMPRE la primera
                # pestaña -- si necesitas otra, usa get_sheet_tab_rows() con gid).
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

    def get_sheet_tab_rows(self, file_id: str, gid: str) -> Optional[Dict]:
        """
        Lee una pestaña ESPECÍFICA de un Google Sheet por su gid, usando la
        API de Sheets (no el export genérico de Drive, que solo trae la
        primera pestaña). Devuelve {"headers": [...], "rows": [[...], ...]}
        o None si no se pudo leer.
        """
        try:
            sheets = self._get_sheets_service()

            # 1) Mapear gid -> nombre real de la pestaña.
            meta = sheets.spreadsheets().get(
                spreadsheetId=file_id, fields="sheets.properties"
            ).execute()
            sheet_title = None
            for s in meta.get("sheets", []):
                props = s.get("properties", {})
                if str(props.get("sheetId")) == str(gid):
                    sheet_title = props.get("title")
                    break

            if not sheet_title:
                print(f"❌ No se encontró la pestaña con gid={gid} en el archivo {file_id}")
                return None

            # 2) Traer todos los valores de esa pestaña.
            result = sheets.spreadsheets().values().get(
                spreadsheetId=file_id, range=sheet_title
            ).execute()
            values = result.get("values", [])
            if not values:
                return {"headers": [], "rows": []}

            headers = values[0]
            rows = values[1:]
            return {"headers": headers, "rows": rows, "sheet_title": sheet_title}
        except Exception as e:  # noqa: BLE001
            print(f"❌ Error leyendo pestaña gid={gid} de {file_id}: {e}")
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

    async def get_all_documents_content_with_type(
        self,
        folder_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Descarga todos los documentos con metadata completa, combinando
        carpetas (`folder_ids`) y archivos sueltos (`file_ids`).
        - PDF: retorna bytes para Document AI.
        - XLSX/XLS: convierte a texto con openpyxl.
        - Google Sheets / Docs: exportado y decodificado como texto (primera pestaña).
        - Resto: texto decodificado.

        NOTA: para leer una pestaña específica de un Google Sheet por gid, no
        uses este método -- usa gdrive_service.get_sheet_tab_rows() directo,
        como hace servers_kb/service.py cuando settings.GDRIVE_SERVERS_SHEET_GID
        está configurado.
        """
        docs = await self.list_documents(folder_ids=folder_ids, file_ids=file_ids)
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

    async def get_all_documents_content(
        self,
        folder_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Compatibilidad con código anterior (solo entradas con texto)."""
        docs = await self.get_all_documents_content_with_type(folder_ids=folder_ids, file_ids=file_ids)
        return [d for d in docs if d.get("content")]

    def is_configured(
        self,
        folder_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> bool:
        """Verifica si Google Drive está configurado: credenciales presentes
        Y (al menos una carpeta O al menos un archivo suelto) configurados."""
        import os

        roots = folder_ids if folder_ids is not None else settings.get_gdrive_folder_ids()
        explicit_files = file_ids or []
        return bool(
            (roots or explicit_files)
            and settings.GOOGLE_APPLICATION_CREDENTIALS
            and os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)
        )


gdrive_service = GoogleDriveService()