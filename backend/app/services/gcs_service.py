"""
Servicio de Google Cloud Storage.
Almacena imágenes enviadas por los usuarios de forma temporal.
Las imágenes se eliminan automáticamente a las 24h via lifecycle policy del bucket.
"""

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional
from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import settings


class GCSService:
    """
    Gestiona la subida y recuperación de imágenes en Cloud Storage.
    Carpeta: botiq-images/{year}/{month}/{day}/{uuid}.{ext}
    """

    MIME_TO_EXT = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }

    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self._client: Optional[storage.Client] = None

    def _get_client(self) -> storage.Client:
        if self._client is None:
            if settings.GOOGLE_APPLICATION_CREDENTIALS:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS
                )
                self._client = storage.Client(
                    project=settings.GCP_PROJECT_ID,
                    credentials=credentials,
                )
            else:
                self._client = storage.Client(project=settings.GCP_PROJECT_ID)
        return self._client

    async def upload_image(
        self,
        image_base64: str,
        mime_type: str = "image/jpeg",
        conversation_id: Optional[str] = None,
    ) -> str:
        """
        Sube una imagen a GCS y retorna la URL pública firmada.

        Args:
            image_base64: Imagen en base64
            mime_type: Tipo MIME
            conversation_id: ID de la conversación (para organizar)

        Returns:
            URL de la imagen en GCS (gs://bucket/path)
        """
        client = self._get_client()
        bucket = client.bucket(self.bucket_name)

        # Generar path organizado por fecha
        now = datetime.now(timezone.utc)
        ext = self.MIME_TO_EXT.get(mime_type, "jpg")
        file_name = f"botiq-images/{now.year}/{now.month:02d}/{now.day:02d}/{uuid.uuid4()}.{ext}"

        blob = bucket.blob(file_name)
        image_bytes = base64.b64decode(image_base64)

        blob.upload_from_string(image_bytes, content_type=mime_type)

        return f"gs://{self.bucket_name}/{file_name}"

    async def delete_image(self, gcs_url: str) -> bool:
        """Elimina una imagen de GCS dado su URL gs://."""
        try:
            # Extraer path del URL gs://bucket/path
            path = gcs_url.replace(f"gs://{self.bucket_name}/", "")
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(path)
            blob.delete()
            return True
        except Exception as e:
            print(f"Error eliminando imagen de GCS: {e}")
            return False


gcs_service = GCSService()
