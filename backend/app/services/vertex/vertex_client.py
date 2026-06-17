"""Cliente base Vertex AI con manejo graceful si no hay credenciales."""
import os
import vertexai
from app.core.config import settings

_initialized = False


def init_vertex_ai() -> bool:
    global _initialized
    if _initialized:
        return True
    if not settings.GCP_PROJECT_ID:
        print("⚠️  GCP_PROJECT_ID no configurado — modo demo activo")
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
        print(f"✅ Vertex AI inicializado — Proyecto: {settings.GCP_PROJECT_ID}")
        return True
    except Exception as e:
        print(f"⚠️  Vertex AI error: {e}")
        return False


def is_vertex_available() -> bool:
    return _initialized


try:
    init_vertex_ai()
except Exception:
    pass


