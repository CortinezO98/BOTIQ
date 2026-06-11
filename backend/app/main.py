"""
BOTIQ — Corporate Intelligent Chatbot
Entry point principal de la aplicación FastAPI.
Referencia: SWEBOK v4 — Arquitectura en capas, separación de responsabilidades.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import engine, Base
from app.api.v1 import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación.
    Inicializa recursos al arrancar y los libera al cerrar.
    """
    # Arranque: crear tablas si no existen (en producción usar Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ BOTIQ Backend iniciado correctamente")
    yield
    # Cierre: liberar recursos
    await engine.dispose()
    print("🛑 BOTIQ Backend detenido")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Corporate Intelligent Chatbot con Vertex AI",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Rutas ───────────────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}
