from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.v1 import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} iniciado [{settings.ENVIRONMENT}]")
    print(f"   GCP: {settings.GCP_PROJECT_ID or 'NO CONFIGURADO — modo demo'}")
    print(f"   Drive: {settings.GDRIVE_FOLDER_ID or 'NO CONFIGURADO'}")
    yield
    print(f"🛑 {settings.APP_NAME} detenido")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Corporate Intelligent Chatbot — Vertex AI · RAG · Google Drive",
    docs_url="/docs",
    redoc_url="/redoc",
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
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
