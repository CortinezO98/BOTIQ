"""
Módulo de validación de servidores.
CORRECCIÓN: mock SOLO en development/test. En producción → error real.
"""
import httpx
from typing import Dict, Optional
from datetime import datetime

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service

SYSTEM_PROMPT = """Eres un especialista en infraestructura de TI.
Analiza el estado actual de los servidores corporativos:

{server_data}

Proporciona:
1. Resumen ejecutivo (1-2 líneas)
2. Servidores con problemas críticos (si hay)
3. Alertas de rendimiento (CPU > 80%, RAM > 85%, Disco > 90%)
4. Recomendaciones de acción inmediata

Responde en español. Sé específico con nombres de servidores.
"""

NO_API_CONFIGURED = (
    "La API del tablero de servidores no está configurada. "
    "Por favor configura SERVER_DASHBOARD_API_URL y SERVER_DASHBOARD_API_KEY en el archivo .env."
)

API_ERROR_PROD = (
    "No fue posible consultar el tablero de servidores en este momento. "
    "Por favor verifica la conectividad con la API del tablero o contacta al equipo de infraestructura."
)


class ServerMonitorService:

    async def fetch_server_status(self) -> Dict:
        """
        Obtiene estado de servidores.
        - Sin configuración → error claro
        - Con configuración → datos reales o error descriptivo
        - Solo en development → datos demo si no hay API
        """
        if not settings.SERVER_DASHBOARD_API_URL:
            if settings.ENVIRONMENT in ("development", "test"):
                return self._mock_data()
            return {"error": True, "message": NO_API_CONFIGURED, "servers": []}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.SERVER_DASHBOARD_API_URL}/servers/status",
                    headers={"Authorization": f"Bearer {settings.SERVER_DASHBOARD_API_KEY}"},
                )
                resp.raise_for_status()
                data = resp.json()
                # Guardar snapshot en BD (async, no bloquea)
                return data

        except httpx.TimeoutException:
            msg = "Timeout al consultar el tablero de servidores (>10s)"
        except httpx.HTTPStatusError as e:
            msg = f"Error HTTP {e.response.status_code} al consultar el tablero"
        except Exception as e:
            msg = f"Error de conexión con el tablero: {str(e)}"

        if settings.ENVIRONMENT in ("development", "test"):
            print(f"⚠️  {msg} — usando datos demo")
            return {**self._mock_data(), "warning": msg}

        return {"error": True, "message": API_ERROR_PROD, "servers": []}

    async def analyze_and_respond(
        self,
        user_query: str,
        image_analysis: Optional[str] = None,
    ) -> Dict:
        server_data = await self.fetch_server_status()

        if server_data.get("error"):
            return {
                "text": server_data.get("message", API_ERROR_PROD),
                "tokens_used": 0,
                "response_time_ms": 0,
                "raw_server_data": server_data,
            }

        summary = self._format(server_data)
        if image_analysis:
            summary += f"\n\nCaptura del usuario: {image_analysis}"
        if server_data.get("warning"):
            summary += f"\n\n⚠️ Nota: {server_data['warning']}"

        result = await gemini_text_service.generate(
            prompt=user_query,
            system_instruction=SYSTEM_PROMPT.format(server_data=summary),
            temperature=0.1,
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "raw_server_data": server_data,
            "queried_at": datetime.utcnow().isoformat(),
        }

    def _format(self, data: Dict) -> str:
        servers = data.get("servers", [])
        if not servers:
            return "No hay datos de servidores disponibles."
        lines = []
        for s in servers:
            icon = "✅" if s.get("is_healthy") else "❌"
            cpu = s.get("cpu_usage", "N/A")
            mem = s.get("memory_usage", "N/A")
            disk = s.get("disk_usage", "N/A")
            # Agregar alertas automáticas
            alerts = []
            if isinstance(cpu, (int, float)) and cpu > 80:
                alerts.append(f"⚠️ CPU ALTA: {cpu}%")
            if isinstance(mem, (int, float)) and mem > 85:
                alerts.append(f"⚠️ RAM ALTA: {mem}%")
            if isinstance(disk, (int, float)) and disk > 90:
                alerts.append(f"⚠️ DISCO CRÍTICO: {disk}%")
            alert_str = " | ".join(alerts) if alerts else ""
            lines.append(
                f"{icon} {s.get('name', 'N/A')} | Estado: {s.get('status')} | "
                f"CPU: {cpu}% | RAM: {mem}% | Disco: {disk}% {alert_str}"
            )
        last = data.get("last_updated", "")
        header = f"Última actualización: {last}\n" if last else ""
        return header + "\n".join(lines)

    def _mock_data(self) -> Dict:
        return {
            "servers": [
                {"name": "Servidor-APP-01", "status": "up",       "is_healthy": True,  "cpu_usage": 45, "memory_usage": 67, "disk_usage": 55},
                {"name": "Servidor-DB-01",  "status": "up",       "is_healthy": True,  "cpu_usage": 23, "memory_usage": 81, "disk_usage": 70},
                {"name": "Servidor-WEB-01", "status": "degraded", "is_healthy": False, "cpu_usage": 89, "memory_usage": 92, "disk_usage": 45},
            ],
            "last_updated": datetime.utcnow().isoformat(),
            "_demo": True,
        }


server_monitor_service = ServerMonitorService()
