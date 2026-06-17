from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_support
from app.core.config import settings
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.modules.support_rag.service import support_rag_service
from app.services.gdrive_service import gdrive_service

router = APIRouter()


async def _run_sync(force: bool):
    """Tarea en segundo plano: usa su propia sesión de BD (no la del request)."""
    async with AsyncSessionLocal() as db:
        try:
            result = await support_rag_service.sync_knowledge_base(db, force=force)
            print(f"🔄 Sincronización finalizada: {result}")
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            print(f"❌ Sincronización falló: {exc}")


@router.post("/sync-knowledge-base")
async def sync_kb(
    bg: BackgroundTasks,
    force: bool = Query(False, description="true = reindexa TODO; false = solo nuevos/modificados"),
    _: User = Depends(require_support),
):
    """
    Sincroniza la base de conocimiento desde Google Drive. Ejecuta en background.
    Por defecto es INCREMENTAL (solo documentos nuevos o modificados).
    Usa ?force=true para forzar la reindexación completa.
    """
    if not gdrive_service.is_configured():
        return {
            "message": "Google Drive no configurado",
            "instructions": [
                "1. Crea/identifica la carpeta en Google Drive",
                "2. Compártela con el Service Account (Lector)",
                "3. Agrega GDRIVE_FOLDER_ID (o GDRIVE_FOLDER_IDS) en backend/.env",
                "4. Reinicia el backend",
            ],
        }
    bg.add_task(_run_sync, force)
    return {
        "message": "Sincronización iniciada en background"
        + (" (reindexación completa)" if force else " (incremental)"),
        "mode": "full" if force else "incremental",
        "drive_configured": True,
    }


@router.get("/knowledge-base/status")
async def kb_status(_: User = Depends(require_support)):
    try:
        col = support_rag_service._get_collection()
        folder_ids = settings.get_gdrive_folder_ids()
        return {
            "status": "active",
            "total_chunks": col.count(),
            "drive_configured": gdrive_service.is_configured(),
            "drive_folder_count": len(folder_ids),
            "drive_folder_ids": folder_ids or ["No configurado"],
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": str(e)}


@router.get("/knowledge-base/documents")
async def kb_documents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    """Lista los documentos indexados con su estado (para el frontend)."""
    docs = await support_rag_service.list_documents(db)
    summary = {
        "total": len(docs),
        "indexed": sum(1 for d in docs if d["status"] == "indexed"),
        "failed": sum(1 for d in docs if d["status"] == "failed"),
        "total_chunks": sum(d["chunk_count"] for d in docs),
    }
    return {"summary": summary, "documents": docs}


@router.post("/knowledge-base/documents/{file_id}/reindex")
async def kb_reindex_document(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    """Reindexa un único documento por su file_id de Google Drive."""
    return await support_rag_service.reindex_document(db, file_id)
