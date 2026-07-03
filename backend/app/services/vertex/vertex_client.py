"""Cliente base Vertex AI con manejo graceful si no hay credenciales."""
import os
import vertexai

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__, service="vertex_ai")

_initialized = False


def init_vertex_ai() -> bool:
    global _initialized
    if _initialized:
        return True
    if not settings.GCP_PROJECT_ID:
        logger.warning("vertex_not_configured", reason="GCP_PROJECT_ID vacío — modo demo activo")
        return False
    try:
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        if creds_path and os.path.exists(creds_path):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION, credentials=creds)
        else:
            vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        _initialized = True
        logger.info("vertex_initialized", project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        return True
    except Exception as exc:
        logger.error("vertex_init_failed", error=str(exc), project=settings.GCP_PROJECT_ID)
        return False


def is_vertex_available() -> bool:
    return _initialized


try:
    init_vertex_ai()
except Exception:
    pass