from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "BOTIQ"
    APP_VERSION: str = "1.3.0"
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

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "botiq_knowledge_base"

    # API externa de estados / disponibilidad de aplicativos.
    # Esta API es insumo interno del bot, no se expone directamente al usuario.
    APPLICATION_STATUS_API_URL: str = ""
    APPLICATION_STATUS_API_KEY: str = ""
    APPLICATION_STATUS_TIMEOUT_SECONDS: int = 10

    # Compatibilidad con el módulo antiguo de servidores.
    SERVER_DASHBOARD_API_URL: str = ""
    SERVER_DASHBOARD_API_KEY: str = ""

    # Integración Aranda.
    # Si ARANDA_API_URL está vacío, BOTIQ no crea ticket real y deja el caso marcado como elegible.
    ARANDA_API_URL: str = ""
    ARANDA_API_KEY: str = ""
    ARANDA_PROJECT_ID: str = ""
    ARANDA_CATEGORY_ID: str = ""
    ARANDA_SERVICE_ID: str = ""
    ARANDA_TIMEOUT_SECONDS: int = 15

    # Controles de consumo y seguridad conversacional.
    MAX_QUESTIONS_PER_SESSION: int = 8
    MAX_OUT_OF_SCOPE_PER_SESSION: int = 1
    MAX_MESSAGE_LENGTH: int = 1200
    MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET: int = 2
    REQUIRE_SUPPORT_NETWORK_VALIDATION: bool = True
    SUPPORT_ALLOWED_EMAIL_DOMAINS: str = "iq-online.com"

    BUSINESS_SCOPE_KEYWORDS: str = (
        "portal,sistema,aplicacion,aplicación,aplicativo,app,url,pagina,página,ip,"
        "correo,outlook,excel,word,teams,vpn,contraseña,password,login,acceso,"
        "servidor,server,base de conocimiento,documentación,documentacion,"
        "procedimiento,incidente,soporte,aranda,ticket,red,firewall,certificado,"
        "ssl,backup,memoria,cpu,disco,latencia,caido,caído,no responde,error"
    )

    OUT_OF_SCOPE_KEYWORDS: str = (
        "chiste,novia,novio,apuesta,casino,política,politica,religión,religion,"
        "sexo,droga,drogas,futbol,fútbol,receta,cocina,pelicula,película,"
        "tarea escolar,poema,cancion,canción,instagram,tiktok,horoscopo,horóscopo"
    )

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:5180,http://localhost:5190,http://localhost:3000"

    def get_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    def get_support_allowed_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.SUPPORT_ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]

    def get_business_keywords(self) -> List[str]:
        return [k.strip().lower() for k in self.BUSINESS_SCOPE_KEYWORDS.split(",") if k.strip()]

    def get_out_of_scope_keywords(self) -> List[str]:
        return [k.strip().lower() for k in self.OUT_OF_SCOPE_KEYWORDS.split(",") if k.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
