from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "BOTIQ"
    APP_VERSION: str = "1.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql://botiq_user:botiq_pass@db:5432/botiq_db"

    SECRET_KEY: str = "dev-secret-change-in-production-32chars!!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    VERTEX_FAST_MODEL: str = "gemini-2.5-flash"
    VERTEX_REASONING_MODEL: str = "gemini-2.5-pro"
    VERTEX_MULTIMODAL_MODEL: str = "gemini-2.5-flash"
    VERTEX_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"

    @property
    def VERTEX_GEMINI_MODEL(self) -> str:
        return self.VERTEX_FAST_MODEL

    @property
    def VERTEX_VISION_MODEL(self) -> str:
        return self.VERTEX_MULTIMODAL_MODEL

    RAG_TOP_K: int = 5
    RAG_MIN_CONFIDENCE: float = 0.72
    MAX_OUTPUT_TOKENS: int = 1024
    VERTEX_TIMEOUT_SECONDS: int = 30

    DOCUMENT_AI_PROCESSOR_ID: str = ""
    DOCUMENT_AI_LOCATION: str = "us"

    GDRIVE_FOLDER_ID: str = ""

    GCS_BUCKET_NAME: str = "botiq-images-bucket"

    SERVER_DASHBOARD_API_URL: str = ""
    SERVER_DASHBOARD_API_KEY: str = ""

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "botiq_knowledge_base"

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
