from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import router as api_v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} iniciado [{settings.ENVIRONMENT}]")
    print(f"   GCP: {settings.GCP_PROJECT_ID or 'NO CONFIGURADO — modo demo'}")
    print(f"   Drive: {len(settings.get_gdrive_folder_ids())} carpeta(s) configurada(s)")
    yield
    print(f"🛑 {settings.APP_NAME} detenido")


IS_PRODUCTION = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Corporate Intelligent Chatbot — Vertex AI · RAG · Google Drive",
    # Seguridad: en producción no se exponen /docs, /redoc ni /openapi.json.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
    lifespan=lifespan,
)

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
    """Liveness: el proceso responde."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT, "version": settings.APP_VERSION}


@app.get("/ready", tags=["Health"])
async def ready():
    """Readiness: dependencias críticas disponibles (PostgreSQL)."""
    checks = {"database": "unknown"}
    overall = "ready"

    try:
        from app.db.session import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
        overall = "not_ready"

    return {"status": overall, "checks": checks}
