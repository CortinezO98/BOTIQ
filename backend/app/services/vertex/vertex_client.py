"""
Cliente base para Vertex AI.
Inicializa la autenticación con Google Cloud usando ADC o Service Account.
"""

import vertexai
from google.oauth2 import service_account
from google.auth import default as google_auth_default
import os

from app.core.config import settings


def init_vertex_ai():
    """
    Inicializa Vertex AI con las credenciales configuradas.
    - En desarrollo: usa el archivo JSON del Service Account
    - En producción (GKE/Cloud Run): usa Application Default Credentials (ADC)
    """
    credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS

    if credentials_path and os.path.exists(credentials_path):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        vertexai.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
            credentials=credentials,
        )
    else:
        # Usar Application Default Credentials
        credentials, project = google_auth_default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        vertexai.init(
            project=settings.GCP_PROJECT_ID or project,
            location=settings.GCP_LOCATION,
            credentials=credentials,
        )

    print(f"✅ Vertex AI inicializado — Proyecto: {settings.GCP_PROJECT_ID}, Región: {settings.GCP_LOCATION}")


# Inicializar al importar el módulo
try:
    init_vertex_ai()
except Exception as e:
    print(f"⚠️ Vertex AI no inicializado (modo local sin credenciales): {e}")
