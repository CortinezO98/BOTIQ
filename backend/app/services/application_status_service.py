from typing import Any, Dict, Optional
import time

import httpx

from app.core.config import settings


class ApplicationStatusService:
    """
    Consume la API externa de estados de aplicativos/servidores.

    Esta API NO se expone al empleado. Solo se usa como insumo del bot para responder:
    - si una URL está caída
    - si un aplicativo tiene degradación
    - si hay incidentes conocidos
    - si existe información operativa del servidor asociado
    """

    async def lookup(self, url: Optional[str] = None, ip: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
        if not url and not ip and not query:
            return {"configured": self.is_configured(), "found": False, "message": "Sin URL, IP o criterio de búsqueda."}

        if not self.is_configured():
            return self._demo_lookup(url=url, ip=ip, query=query)

        params = {}
        if url:
            params["url"] = url
        if ip:
            params["ip"] = ip
        if query:
            params["q"] = query

        headers = {}
        if settings.APPLICATION_STATUS_API_KEY:
            headers["Authorization"] = f"Bearer {settings.APPLICATION_STATUS_API_KEY}"

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=settings.APPLICATION_STATUS_TIMEOUT_SECONDS) as client:
                response = await client.get(settings.APPLICATION_STATUS_API_URL.rstrip("/") + "/status", params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                data["_response_time_ms"] = round((time.time() - start) * 1000, 2)
                data["_source"] = "external_api"
                data["configured"] = True
                return data
        except Exception as exc:
            return {
                "configured": True,
                "found": False,
                "status": "unknown",
                "message": f"No fue posible consultar la API de estados: {exc}",
                "_source": "external_api_error",
            }

    def is_configured(self) -> bool:
        return bool(settings.APPLICATION_STATUS_API_URL)

    def _demo_lookup(self, url: Optional[str], ip: Optional[str], query: Optional[str]) -> Dict[str, Any]:
        target = url or ip or query or "servicio"
        lowered = target.lower()

        if any(k in lowered for k in ["down", "caido", "caído", "error500", "500"]):
            return {
                "configured": False,
                "found": True,
                "status": "down",
                "service_name": target,
                "message": "Modo demo: el servicio aparece como caído.",
                "details": {"http_status": 500, "last_check": "demo"},
                "_source": "demo",
            }

        return {
            "configured": False,
            "found": True,
            "status": "up",
            "service_name": target,
            "message": "Modo demo: el servicio aparece operativo.",
            "details": {"http_status": 200, "last_check": "demo"},
            "_source": "demo",
        }

    def format_for_prompt(self, status: Dict[str, Any]) -> str:
        if not status:
            return "No hay información de estado disponible."

        return (
            f"Estado aplicativo/servidor:\n"
            f"- Fuente: {status.get('_source', 'desconocida')}\n"
            f"- Encontrado: {status.get('found', 'N/A')}\n"
            f"- Servicio: {status.get('service_name') or status.get('name') or 'N/A'}\n"
            f"- Estado: {status.get('status', 'unknown')}\n"
            f"- Mensaje: {status.get('message', 'N/A')}\n"
            f"- Detalles: {status.get('details', {})}"
        )


application_status_service = ApplicationStatusService()


