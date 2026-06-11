"""
Configuración centralizada BOTIQ — versión mejorada.
Modelos Vertex AI separados por propósito.
"""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "BOTIQ"
    APP_VERSION: str = "1.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ── Base de Datos ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://botiq_user:botiq_pass@db:5432/botiq_db"

    # ── Seguridad JWT ─────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ── Google Cloud ──────────────────────────────────────────────────────────
    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ── Vertex AI — Modelos separados por propósito ───────────────────────────
    VERTEX_FAST_MODEL: str = "gemini-2.5-flash"        # FAQ, empleados, clasificador
    VERTEX_REASONING_MODEL: str = "gemini-2.5-pro"     # RAG, análisis complejo
    VERTEX_MULTIMODAL_MODEL: str = "gemini-2.5-flash"  # Análisis de imágenes
    VERTEX_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"

    # ── Vertex AI — Compatibilidad (alias) ────────────────────────────────────
    @property
    def VERTEX_GEMINI_MODEL(self) -> str:
        return self.VERTEX_FAST_MODEL
    @property
    def VERTEX_VISION_MODEL(self) -> str:
        return self.VERTEX_MULTIMODAL_MODEL

    # ── Parámetros RAG ────────────────────────────────────────────────────────
    RAG_TOP_K: int = 5
    RAG_MIN_CONFIDENCE: float = 0.72
    MAX_OUTPUT_TOKENS: int = 1024
    VERTEX_TIMEOUT_SECONDS: int = 30

    # ── Vertex AI Vector Search (opcional, producción) ────────────────────────
    VERTEX_VECTOR_SEARCH_INDEX_ID: str = ""
    VERTEX_VECTOR_SEARCH_ENDPOINT_ID: str = ""

    # ── Document AI ───────────────────────────────────────────────────────────
    DOCUMENT_AI_PROCESSOR_ID: str = ""
    DOCUMENT_AI_LOCATION: str = "us"

    # ── Google Drive ──────────────────────────────────────────────────────────
    GDRIVE_FOLDER_ID: str = ""

    # ── Cloud Storage ─────────────────────────────────────────────────────────
    GCS_BUCKET_NAME: str = "botiq-images-bucket"

    # ── API Servidores ────────────────────────────────────────────────────────
    SERVER_DASHBOARD_API_URL: str = ""
    SERVER_DASHBOARD_API_KEY: str = ""

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "botiq_knowledge_base"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    def get_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
