from fastapi import APIRouter, Depends
from app.api.deps import require_support
from app.models.user import User
from app.modules.server_monitor.service import server_monitor_service

router = APIRouter()


@router.get("/status")
async def get_status(_: User = Depends(require_support)):
    return await server_monitor_service.fetch_server_status()


@router.get("/analysis")
async def get_analysis(_: User = Depends(require_support)):
    return await server_monitor_service.analyze_and_respond(
        "Dame un resumen del estado actual de todos los servidores"
    )
