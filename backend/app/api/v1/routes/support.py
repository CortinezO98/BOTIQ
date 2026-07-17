import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_support
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.modules.support_rag.service import support_rag_service
from app.services.gdrive_service import gdrive_service

router = APIRouter()

logger = get_logger(__name__, service="support_routes")

# Cada cuánto corre la sincronización automática en background.
# 30 minutos porque la hoja de memoria/RAM de servidores se actualiza con
# esa frecuencia -- no tiene sentido esperar más ni tiene caso correr más
# seguido (el sync incremental de 18 docs, sin cambios, igual tarda unos
# segundos en listar Drive).
SYNC_INTERVAL_SECONDS = 30 * 60

# Evita que dos sincronizaciones corran en paralelo (manual + programada, o
# dos programadas si el intervalo se solapara con una corrida lenta). Cada
# background task tiene su propia sesión de BD y hace un solo commit() al
# final del batch completo -- si corren concurrentes, la que termina de
# última pisa por completo el resultado de la otra (last-write-wins).
#
# OJO -- esta protección vive en memoria de UN proceso. Si el día de mañana
# el backend corre con varios workers (ej. gunicorn -w 4), cada worker tiene
# su propio _sync_lock / _sync_in_progress y esto deja de proteger entre
# procesos. Mientras el backend corra como un solo proceso (como hoy en dev
# y como está en docker-compose), es suficiente.
_sync_lock = asyncio.Lock()
_sync_in_progress = False

# Último resultado conocido del sync (éxito o error), para que el frontend
# pueda mostrarlo aunque haya cerrado la pestaña o perdido el polling.
_last_sync_result: Optional[Dict[str, Any]] = None
_last_sync_error: Optional[str] = None
_last_sync_finished_at: Optional[str] = None
_last_sync_trigger: Optional[str] = None  # "manual" | "scheduled"

_scheduler_task: Optional[asyncio.Task] = None


async def _run_sync(force: bool, trigger: str = "manual"):
    """Tarea en segundo plano: usa su propia sesión de BD (no la del request)."""
    global _sync_in_progress, _last_sync_result, _last_sync_error, _last_sync_finished_at, _last_sync_trigger
    _last_sync_trigger = trigger
    async with AsyncSessionLocal() as db:
        try:
            result = await support_rag_service.sync_knowledge_base(db, force=force)
            logger.info("kb_sync_finished", result=result, trigger=trigger)
            _last_sync_result = result
            _last_sync_error = None
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error("kb_sync_failed", error=str(exc), trigger=trigger)
            _last_sync_result = None
            _last_sync_error = str(exc)
        finally:
            _last_sync_finished_at = datetime.now(timezone.utc).isoformat()
            _sync_in_progress = False


async def _try_start_sync(force: bool, trigger: str) -> bool:
    """Intenta tomar el lock y lanzar el sync. Devuelve False si ya hay uno corriendo."""
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
    """Corre en background durante toda la vida del proceso: cada
    SYNC_INTERVAL_SECONDS intenta una sincronización incremental automática."""
    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

            if not gdrive_service.is_configured():
                logger.debug("kb_scheduled_sync_skipped_not_configured")
                continue

            started = await _try_start_sync(force=False, trigger="scheduled")
            if started:
                logger.info("kb_scheduled_sync_started")
            else:
                logger.info("kb_scheduled_sync_skipped_already_running")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Un error inesperado en el loop no debe matar el scheduler --
            # lo registramos y seguimos esperando el siguiente ciclo.
            logger.error("kb_scheduler_loop_error", error=str(exc))


def start_scheduler():
    """Llamar una vez desde el lifespan de la app al arrancar."""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduled_sync_loop())
        logger.info("kb_scheduler_started", interval_seconds=SYNC_INTERVAL_SECONDS)


def stop_scheduler():
    """Llamar desde el lifespan al apagar la app."""
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("kb_scheduler_stopped")


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

    Nota: además de este endpoint manual, hay un sync automático incremental
    cada 30 minutos (ver start_scheduler) para reflejar cambios como la hoja
    de memoria/RAM de servidores sin depender de que alguien le dé clic.
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

    started = await _try_start_sync(force=force, trigger="manual")
    if not started:
        return {
            "message": "Ya hay una sincronización en curso. Espera a que termine antes de lanzar otra.",
            "mode": "full" if force else "incremental",
            "drive_configured": True,
            "already_running": True,
        }

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