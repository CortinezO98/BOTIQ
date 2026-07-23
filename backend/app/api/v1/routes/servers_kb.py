from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_support
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.modules.servers_kb.service import servers_kb_service

router = APIRouter()
logger = get_logger(__name__, service="servers_kb_routes")

SYNC_INTERVAL_SECONDS = max(
    60,
    int(settings.SERVERS_KB_SYNC_INTERVAL_MINUTES) * 60,
)

# El lock local evita duplicados dentro de un proceso. El advisory lock de
# PostgreSQL, tomado en _run_sync(), evita que dos workers de Gunicorn o dos
# instancias ejecuten la misma sincronización al mismo tiempo.
_sync_lock = asyncio.Lock()
_sync_in_progress = False
_SYNC_ADVISORY_LOCK_KEY = 2026072301

_last_sync_result: Optional[Dict[str, Any]] = None
_last_sync_error: Optional[str] = None
_last_sync_finished_at: Optional[str] = None
_last_sync_trigger: Optional[str] = None
_scheduler_task: Optional[asyncio.Task] = None


class AskRequest(BaseModel):
    message: str


async def _try_database_lock(db: AsyncSession) -> bool:
    """Obtiene un lock transaccional distribuido en PostgreSQL.

    Se libera automáticamente al hacer commit/rollback. El servicio de sync
    realiza un único commit al finalizar el lote, por lo que el lock cubre toda
    la lectura de Drive, cálculo de hash e indexación en ChromaDB.
    """
    try:
        result = await db.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": _SYNC_ADVISORY_LOCK_KEY},
        )
        return bool(result.scalar())
    except Exception as exc:  # noqa: BLE001
        logger.error("servers_kb_advisory_lock_error", error=str(exc))
        return False


async def _run_sync(force: bool, trigger: str = "manual") -> None:
    global _sync_in_progress
    global _last_sync_result
    global _last_sync_error
    global _last_sync_finished_at
    global _last_sync_trigger

    _last_sync_trigger = trigger
    async with AsyncSessionLocal() as db:
        try:
            lock_acquired = await _try_database_lock(db)
            if not lock_acquired:
                _last_sync_result = {
                    "status": "skipped",
                    "reason": "distributed_lock_busy",
                    "message": (
                        "Otra instancia de BOTIQ ya está sincronizando la base "
                        "de servidores."
                    ),
                }
                _last_sync_error = None
                logger.info(
                    "servers_kb_sync_skipped_distributed_lock",
                    trigger=trigger,
                )
                await db.rollback()
                return

            result = await servers_kb_service.sync_knowledge_base(
                db,
                force=force,
            )
            logger.info(
                "servers_kb_sync_finished",
                result=result,
                trigger=trigger,
            )
            _last_sync_result = result
            _last_sync_error = None
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error(
                "servers_kb_sync_failed",
                error=str(exc),
                trigger=trigger,
            )
            _last_sync_result = None
            _last_sync_error = str(exc)
        finally:
            _last_sync_finished_at = datetime.now(timezone.utc).isoformat()
            _sync_in_progress = False


async def _try_start_sync(force: bool, trigger: str) -> bool:
    global _sync_in_progress
    global _last_sync_result
    global _last_sync_error

    async with _sync_lock:
        if _sync_in_progress:
            return False
        _sync_in_progress = True
        _last_sync_result = None
        _last_sync_error = None

    asyncio.create_task(_run_sync(force, trigger=trigger))
    return True


async def _scheduled_sync_loop() -> None:
    if settings.SERVERS_KB_SYNC_ON_STARTUP:
        try:
            await asyncio.sleep(
                max(0, int(settings.SERVERS_KB_STARTUP_DELAY_SECONDS))
            )
            if servers_kb_service.is_configured():
                started = await _try_start_sync(
                    force=False,
                    trigger="startup",
                )
                if started:
                    logger.info("servers_kb_startup_sync_started")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("servers_kb_startup_sync_error", error=str(exc))

    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)

            if not servers_kb_service.is_configured():
                logger.debug("servers_kb_scheduled_sync_skipped_not_configured")
                continue

            started = await _try_start_sync(
                force=False,
                trigger="scheduled",
            )
            if started:
                logger.info("servers_kb_scheduled_sync_started")
            else:
                logger.info(
                    "servers_kb_scheduled_sync_skipped_already_running"
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("servers_kb_scheduler_loop_error", error=str(exc))


def start_scheduler() -> None:
    """Inicia el scheduler incremental de servidores una vez por proceso."""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduled_sync_loop())
        logger.info(
            "servers_kb_scheduler_started",
            interval_seconds=SYNC_INTERVAL_SECONDS,
            interval_minutes=settings.SERVERS_KB_SYNC_INTERVAL_MINUTES,
            sync_on_startup=settings.SERVERS_KB_SYNC_ON_STARTUP,
        )


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("servers_kb_scheduler_stopped")


@router.post("/sync-knowledge-base")
async def sync_servers_kb(
    force: bool = Query(
        False,
        description=(
            "true = reindexa todo; false = solo archivos nuevos o modificados"
        ),
    ),
    _: User = Depends(require_support),
):
    """Inicia la sincronización en background.

    La ejecución automática usa siempre force=false. Cada 10 minutos revisa
    el Google Sheet, calcula su hash y solo genera embeddings si el contenido
    cambió. force=true queda reservado para una reconstrucción manual completa.
    """
    if not servers_kb_service.is_configured():
        return {
            "message": (
                "Google Drive no configurado para la base de servidores"
            ),
            "instructions": [
                "1. Identifica la carpeta o archivo de servidores en Drive",
                "2. Compártelo con el Service Account como lector",
                (
                    "3. Configura GDRIVE_SERVERS_FOLDER_ID(S) y/o "
                    "GDRIVE_SERVERS_FILE_ID(S)"
                ),
                (
                    "4. Configura GDRIVE_SERVERS_SHEET_GID si la tabla está "
                    "en una pestaña específica"
                ),
                "5. Recrea el backend",
            ],
        }

    started = await _try_start_sync(force=force, trigger="manual")
    if not started:
        return {
            "message": (
                "Ya hay una sincronización de servidores en curso. "
                "Espera a que termine."
            ),
            "mode": "full" if force else "incremental",
            "drive_configured": True,
            "already_running": True,
        }

    return {
        "message": (
            "Sincronización de servidores iniciada en background"
            + (
                " (reindexación completa)"
                if force
                else " (incremental)"
            )
        ),
        "mode": "full" if force else "incremental",
        "drive_configured": True,
    }


@router.get("/knowledge-base/status")
async def servers_kb_status(_: User = Depends(require_support)):
    try:
        collection = servers_kb_service._get_collection()
        folder_ids = settings.get_servers_folder_ids()
        file_ids = settings.get_servers_file_ids()
        return {
            "status": "active",
            "total_chunks": collection.count(),
            "drive_configured": servers_kb_service.is_configured(),
            "drive_folder_count": len(folder_ids),
            "drive_folder_ids": folder_ids,
            "drive_file_count": len(file_ids),
            "drive_file_ids": file_ids,
            "sheet_gid": settings.GDRIVE_SERVERS_SHEET_GID or None,
            "sync_in_progress": _sync_in_progress,
            "last_sync_result": _last_sync_result,
            "last_sync_error": _last_sync_error,
            "last_sync_finished_at": _last_sync_finished_at,
            "last_sync_trigger": _last_sync_trigger,
            "auto_sync_interval_minutes": (
                settings.SERVERS_KB_SYNC_INTERVAL_MINUTES
            ),
            "sync_on_startup": settings.SERVERS_KB_SYNC_ON_STARTUP,
            "stale_after_minutes": settings.SERVERS_KB_STALE_AFTER_MINUTES,
            "health_thresholds": {
                "cpu_pct": settings.SERVERS_KB_CPU_ALERT_PCT,
                "ram_pct": settings.SERVERS_KB_RAM_ALERT_PCT,
                "disk_pct": settings.SERVERS_KB_DISK_ALERT_PCT,
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get("/knowledge-base/documents")
async def servers_kb_documents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    docs = await servers_kb_service.list_documents(db)
    summary = {
        "total": len(docs),
        "indexed": sum(1 for doc in docs if doc["status"] == "indexed"),
        "failed": sum(1 for doc in docs if doc["status"] == "failed"),
        "total_chunks": sum(doc["chunk_count"] for doc in docs),
    }
    return {"summary": summary, "documents": docs}


@router.post("/knowledge-base/documents/{file_id}/reindex")
async def servers_kb_reindex_document(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_support),
):
    return await servers_kb_service.reindex_document(db, file_id)


@router.post("/ask")
async def servers_kb_ask(
    body: AskRequest,
    _: User = Depends(require_support),
):
    """Consulta directa para diagnóstico y pruebas del RAG de servidores."""
    return await servers_kb_service.generate_response(body.message)
