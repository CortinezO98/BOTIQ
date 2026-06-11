"""
Cliente base Vertex AI — inicialización con manejo graceful.
Si no hay credenciales configuradas, el bot opera en modo degradado
(respuestas de fallback) sin crashear el servidor.
"""

import os
import vertexai
from app.core.config import settings

_vertex_initialized = False


def init_vertex_ai() -> bool:
    """
    Inicializa Vertex AI. Retorna True si fue exitoso.
    No lanza excepción si falla — modo degradado.
    """
    global _vertex_initialized

    if _vertex_initialized:
        return True

    if not settings.GCP_PROJECT_ID:
        print("⚠️  GCP_PROJECT_ID no configurado — Vertex AI deshabilitado (modo demo)")
        return False

    try:
        creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
        if creds_path and os.path.exists(creds_path):
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            vertexai.init(
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_LOCATION,
                credentials=credentials,
            )
        else:
            vertexai.init(
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_LOCATION,
            )

        _vertex_initialized = True
        print(f"✅ Vertex AI inicializado — Proyecto: {settings.GCP_PROJECT_ID}")
        return True

    except Exception as e:
        print(f"⚠️  Vertex AI no inicializado: {e}")
        return False


def is_vertex_available() -> bool:
    return _vertex_initialized
