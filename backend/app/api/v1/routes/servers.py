"""Rutas del módulo de validación de servidores."""

from fastapi import APIRouter, Depends
from app.api.deps import require_support
from app.models.user import User
from app.modules.server_monitor.service import server_monitor_service

router = APIRouter()


@router.get("/status")
async def get_server_status(
    current_user: User = Depends(require_support),
):
    """
    Retorna el estado actual de los servidores con análisis de Gemini.
    Solo accesible para ingenieros de soporte y admins.
    """
    server_data = await server_monitor_service.fetch_server_status()
    return server_data


@router.get("/analysis")
async def get_server_analysis(
    current_user: User = Depends(require_support),
):
    """Análisis inteligente del estado de servidores con Gemini."""
    result = await server_monitor_service.analyze_and_respond(
        user_query="Dame un resumen del estado actual de todos los servidores"
    )
    return result
