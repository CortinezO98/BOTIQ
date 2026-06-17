"""Cloud Storage — imágenes temporales del chat (lifecycle: 1 día)."""
import base64, uuid
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings


class GCSService:
    MIME_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage
            from google.oauth2 import service_account
            import os
            if settings.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS
                )
                self._client = storage.Client(project=settings.GCP_PROJECT_ID, credentials=creds)
            else:
                self._client = storage.Client(project=settings.GCP_PROJECT_ID)
        return self._client

    async def upload_image(self, image_b64: str, mime_type: str = "image/jpeg") -> str:
        if not settings.GCS_BUCKET_NAME or not settings.GCP_PROJECT_ID:
            return ""
        try:
            client = self._get_client()
            bucket = client.bucket(settings.GCS_BUCKET_NAME)
            now = datetime.now(timezone.utc)
            ext = self.MIME_EXT.get(mime_type, "jpg")
            path = f"botiq-images/{now.year}/{now.month:02d}/{now.day:02d}/{uuid.uuid4()}.{ext}"
            blob = bucket.blob(path)
            blob.upload_from_string(base64.b64decode(image_b64), content_type=mime_type)
            return f"gs://{settings.GCS_BUCKET_NAME}/{path}"
        except Exception as e:
            print(f"GCS upload error: {e}")
            return ""


gcs_service = GCSService()


