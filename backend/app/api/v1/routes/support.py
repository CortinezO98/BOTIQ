"""Rutas del módulo de soporte RAG."""

from fastapi import APIRouter, Depends, BackgroundTasks
from app.api.deps import require_support
from app.models.user import User
from app.modules.support_rag.service import support_rag_service

router = APIRouter()


@router.post("/sync-knowledge-base")
async def sync_knowledge_base(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_support),
):
    """
    Sincroniza la base de conocimiento desde Google Drive.
    Se ejecuta en background para no bloquear la respuesta.
    """
    background_tasks.add_task(support_rag_service.sync_knowledge_base)
    return {"message": "Sincronización iniciada en background"}


@router.get("/knowledge-base/status")
async def knowledge_base_status(
    current_user: User = Depends(require_support),
):
    """Estado de la base de conocimiento RAG."""
    try:
        collection = support_rag_service._get_collection()
        count = collection.count()
        return {"status": "active", "total_chunks": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
