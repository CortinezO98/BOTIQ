"""
Configuración centralizada de BOTIQ.
Todas las variables de entorno se leen desde aquí.
SWEBOK v4: Gestión de configuración — nunca hardcodear valores sensibles.
"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # ─── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "BOTIQ"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ─── Base de Datos ────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ─── Seguridad JWT ───────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ─── Google Cloud ────────────────────────────────────────────────────────
    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ─── Vertex AI ───────────────────────────────────────────────────────────
    VERTEX_GEMINI_MODEL: str = "gemini-1.5-pro"
    VERTEX_VISION_MODEL: str = "gemini-1.5-pro"
    VERTEX_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"
    VERTEX_VECTOR_SEARCH_INDEX_ID: str = ""
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID: str = ""

    # ─── Document AI ─────────────────────────────────────────────────────────
    DOCUMENT_AI_PROCESSOR_ID: str = ""
    DOCUMENT_AI_LOCATION: str = "us"

    # ─── Google Drive ────────────────────────────────────────────────────────
    GDRIVE_FOLDER_ID: str = ""

    # ─── Cloud Storage ───────────────────────────────────────────────────────
    GCS_BUCKET_NAME: str = "botiq-images-bucket"

    # ─── API Servidores ───────────────────────────────────────────────────────
    SERVER_DASHBOARD_API_URL: str = ""
    SERVER_DASHBOARD_API_KEY: str = ""

    # ─── ChromaDB ────────────────────────────────────────────────────────────
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "botiq_knowledge_base"

    # ─── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
