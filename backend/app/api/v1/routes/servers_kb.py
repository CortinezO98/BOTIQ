import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_support
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.modules.servers_kb.service import servers_kb_service
from app.services.gdrive_service import gdrive_service

router = APIRouter()

logger = get_logger(__name__, service="servers_kb_routes")

# Misma cadencia que se pidió para la hoja de memoria/RAM de servidores.
SYNC_INTERVAL_SECONDS = 30 * 60

# Lock independiente del de support.py -- esta KB tiene su propia carpeta de
# Drive, colección de ChromaDB y tabla, así que un sync de servidores nunca
# debería bloquear ni ser bloqueado por un sync de soporte.
#
# OJO -- igual que en support.py, esta protección vive en memoria de UN
# proceso. Si el backend llegara a correr con varios workers, cada worker
# tendría su propio lock y dejaría de proteger entre procesos.
_sync_lock = asyncio.Lock()
_sync_in_progress = False

_last_sync_result: Optional[Dict[str, Any]] = None
_last_sync_error: Optional[str] = None
_last_sync_finished_at: Optional[str] = None
_last_sync_trigger: Optional[str] = None  # "manual" | "scheduled"

_scheduler_task: Optional[asyncio.Task] = None


class AskRequest(BaseModel):
    message: str


async def _run_sync(force: bool, trigger: str = "manual"):
    global _sync_in_progress, _last_sync_result, _last_sync_error, _last_sync_finished_at, _last_sync_trigger
    _last_sync_trigger = trigger
    async with AsyncSessionLocal() as db:
        try:
            result = await servers_kb_service.sync_knowledge_base(db, force=force)
            logger.info("servers_kb_sync_finished", result=result, trigger=trigger)
            _last_sync_result = result
            _last_sync_error = None
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("servers_kb_sync_failed", error=str(exc), trigger=trigger)
            _last_sync_result = None
            _last_sync_error = str(exc)
        finally:
            _last_sync_finished_at = datetime.now(timezone.utc).isoformat()
            _sync_in_progress = False


async def _try_start_sync(force: bool, trigger: str) -> bool:
    global _sync_in_progress, _last_sync_result, _last_sync_error
    async with _sync_lock:
        if _sync_in_progress:
            return False
        _sync_in_progress = True
        _last_sync_result = None
        _last_sync_error = None

    asyncio.create_task(_run_sync(force, trigger=trigger))
    return True


async def _scheduled_sync_loop():
    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

            if not servers_kb_service.is_configured():
                logger.debug("servers_kb_scheduled_sync_skipped_not_configured")
                continue

            started = await _try_start_sync(force=False, trigger="scheduled")
            if started:
                logger.info("servers_kb_scheduled_sync_started")
            else:
                logger.info("servers_kb_scheduled_sync_skipped_already_running")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("servers_kb_scheduler_loop_error", error=str(exc))


def start_scheduler():
    """Llamar una vez desde el lifespan de la app al arrancar."""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduled_sync_loop())
        logger.info("servers_kb_scheduler_started", interval_seconds=SYNC_INTERVAL_SECONDS)


def stop_scheduler():
    """Llamar desde el lifespan al apagar la app."""
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("servers_kb_scheduler_stopped")


@router.post("/sync-knowledge-base")
async def sync_servers_kb(
    force: bool = Query(False, description="true = reindexa TODO; false = solo nuevos/modificados"),
    _: User = Depends(require_support),
):
    """
    Sincroniza la base de conocimiento de SERVIDORES desde su carpeta/archivo
    de Drive. Ejecuta en background. Además corre automáticamente cada 30
    minutos (ver start_scheduler) para reflejar la hoja de memoria/RAM sin
    depender de que alguien le dé clic.
    """
    if not servers_kb_service.is_configured():
        return {
            "message": "Google Drive no configurado para la base de servidores",
            "instructions": [
                "1. Crea/identifica la carpeta o archivo de servidores en Google Drive",
                "2. Compártelo con el Service Account (Lector)",
                "3. Agrega GDRIVE_SERVERS_FOLDER_ID(S) y/o GDRIVE_SERVERS_FILE_ID(S) en backend/.env",
                "4. Si la tabla vive en una pestaña que no es la primera, agrega GDRIVE_SERVERS_SHEET_GID",
                "5. Reinicia el backend",
            ],
        }

    started = await _try_start_sync(force=force, trigger="manual")
    if not started:
        return {
            "message": "Ya hay una sincronización de servidores en curso. Espera a que termine antes de lanzar otra.",
            "mode": "full" if force else "incremental",
            "drive_configured": True,
            "already_running": True,
        }

    return {
        "message": "Sincronización de servidores iniciada en background"
        + (" (reindexación completa)" if force else " (incremental)"),
        "mode": "full" if force else "incremental",
        "drive_configured": True,
    }


@router.get("/knowledge-base/status")
async def servers_kb_status(_: User = Depends(require_support)):
    try:
        col = servers_kb_service._get_collection()
        folder_ids = settings.get_servers_folder_ids()
        file_ids = settings.get_servers_file_ids()
        return {
            "status": "active",
            "total_chunks": col.count(),
            "drive_configured": servers_kb_service.is_configured(),
            "drive_folder_count": len(folder_ids),
            "drive_folder_ids": folder_ids or ["No configurado"],
            "drive_file_count": len(file_ids),
            "drive_file_ids": file_ids or ["No configurado"],
            "sheet_gid": settings.GDRIVE_SERVERS_SHEET_GID or None,
            "sync_in_progress": _sync_in_progress,
            "last_sync_result": _last_sync_result,
            "last_sync_error": _last_sync_error,
            "last_sync_finished_at": _last_sync_finished_at,
            "last_sync_trigger": _last_sync_trigger,
            "auto_sync_interval_minutes": SYNC_INTERVAL_SECONDS // 60,
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "detail": str(e)}


@router.get("/knowledge-base/documents")
async def servers_kb_documents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    """Lista los documentos indexados de la KB de servidores (para el frontend)."""
    docs = await servers_kb_service.list_documents(db)
    summary = {
        "total": len(docs),
        "indexed": sum(1 for d in docs if d["status"] == "indexed"),
        "failed": sum(1 for d in docs if d["status"] == "failed"),
        "total_chunks": sum(d["chunk_count"] for d in docs),
    }
    return {"summary": summary, "documents": docs}


@router.post("/knowledge-base/documents/{file_id}/reindex")
async def servers_kb_reindex_document(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    """Reindexa un único documento de servidores por su file_id de Google Drive."""
    return await servers_kb_service.reindex_document(db, file_id)


@router.post("/ask")
async def servers_kb_ask(
    body: AskRequest,
    _: User = Depends(require_support),
):
    """
    Endpoint de PRUEBA para validar la KB de servidores sin esperar a que
    esté conectada al chat real (Employee Bot / Support). Úsalo para
    confirmar que la sincronización quedó bien antes de la integración
    final. Ej: {"message": "¿cómo está el servidor AGNES?"}
    """
    return await servers_kb_service.generate_response(body.message)