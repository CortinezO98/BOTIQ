"""Rutas del módulo de soporte RAG."""
from fastapi import APIRouter, Depends, BackgroundTasks
from app.api.deps import require_support
from app.models.user import User
from app.modules.support_rag.service import support_rag_service

router = APIRouter()


@router.post("/sync-knowledge-base")
async def sync_kb(bg: BackgroundTasks, _: User = Depends(require_support)):
    bg.add_task(support_rag_service.sync_knowledge_base)
    return {"message": "Sincronización iniciada en background"}


@router.get("/knowledge-base/status")
async def kb_status(_: User = Depends(require_support)):
    try:
        collection = support_rag_service._get_collection()
        return {"status": "active", "total_chunks": collection.count()}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
