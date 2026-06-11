"""
BOTIQ — Entry point principal FastAPI.
SWEBOK v4: Arquitectura en capas, separación de responsabilidades.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1 import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación."""
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} iniciado")
    print(f"   Entorno: {settings.ENVIRONMENT}")
    print(f"   GCP Project: {settings.GCP_PROJECT_ID or 'NO CONFIGURADO'}")
    yield
    print(f"🛑 {settings.APP_NAME} detenido")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Corporate Intelligent Chatbot — Vertex AI + RAG + Server Monitor",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rutas API v1 ──────────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
