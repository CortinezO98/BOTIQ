from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger

logger = get_logger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.API_RATE_LIMIT],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "botiq_startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        gcp_project=settings.GCP_PROJECT_ID or "demo_mode",
        gdrive_folders=len(settings.get_gdrive_folder_ids()),
        rate_limiting=settings.RATE_LIMIT_ENABLED,
        login_rate_limit=settings.LOGIN_RATE_LIMIT,
        chat_rate_limit=settings.CHAT_RATE_LIMIT,
    )
    yield
    logger.info("botiq_shutdown", app=settings.APP_NAME)


IS_PRODUCTION = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Corporate Intelligent Chatbot — Vertex AI · RAG · Google Drive",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": None if IS_PRODUCTION else "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Liveness: el proceso responde. Incluye estado de Vertex AI."""
    from app.services.vertex.vertex_client import is_vertex_available
    ai_ok = is_vertex_available()
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "ai_available": ai_ok,
        "ai_mode": "vertex_ai" if ai_ok else "demo",
    }


@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness: dependencias críticas disponibles (PostgreSQL + Vertex AI)."""
    from app.services.vertex.vertex_client import is_vertex_available
    checks = {"database": "unknown", "vertex_ai": "ok" if is_vertex_available() else "demo_mode"}
    overall = "ready"

    try:
        from app.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        overall = "not_ready"
        logger.error("readiness_check_failed", error=str(exc))

    return {"status": overall, "checks": checks}