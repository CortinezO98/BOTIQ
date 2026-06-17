import httpx
from typing import Dict, Optional
from datetime import datetime
from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service

SYSTEM = """Eres especialista en infraestructura de TI.
Estado de servidores:
{server_data}

Proporciona:
1. Resumen ejecutivo (1-2 líneas)
2. Servidores con problemas críticos
3. Alertas de rendimiento (CPU>80%, RAM>85%, Disco>90%)
4. Recomendaciones de acción inmediata
Responde en español.
"""


class ServerMonitorService:

    async def fetch_server_status(self) -> Dict:
        if not settings.SERVER_DASHBOARD_API_URL:
            if settings.ENVIRONMENT in ("development", "test"):
                return self._mock()
            return {"error": True, "message": "API de servidores no configurada", "servers": []}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{settings.SERVER_DASHBOARD_API_URL}/servers/status",
                                headers={"Authorization": f"Bearer {settings.SERVER_DASHBOARD_API_KEY}"})
                r.raise_for_status()
                return r.json()
        except Exception as e:
            if settings.ENVIRONMENT in ("development", "test"):
                return {**self._mock(), "warning": str(e)}
            return {"error": True, "message": "No fue posible consultar el tablero de servidores", "servers": []}

    async def analyze_and_respond(self, user_query: str, image_analysis: Optional[str] = None) -> Dict:
        data = await self.fetch_server_status()
        if data.get("error"):
            return {"text": data.get("message", "Error al consultar servidores"), "tokens_used": 0, "response_time_ms": 0}
        summary = self._fmt(data)
        if image_analysis:
            summary += f"\n\nCaptura del usuario: {image_analysis}"
        result = await gemini_text_service.generate(
            prompt=user_query,
            system_instruction=SYSTEM.format(server_data=summary),
            temperature=0.1,
            model=settings.VERTEX_FAST_MODEL,
        )
        return {"text": result["text"], "tokens_used": result.get("tokens_used"),
                "response_time_ms": result.get("response_time_ms"), "raw_server_data": data}

    def _fmt(self, data: Dict) -> str:
        servers = data.get("servers", [])
        lines = []
        for s in servers:
            icon = "✅" if s.get("is_healthy") else "❌"
            cpu, mem, disk = s.get("cpu_usage","N/A"), s.get("memory_usage","N/A"), s.get("disk_usage","N/A")
            alerts = []
            if isinstance(cpu, (int,float)) and cpu > 80: alerts.append(f"⚠️CPU:{cpu}%")
            if isinstance(mem, (int,float)) and mem > 85: alerts.append(f"⚠️RAM:{mem}%")
            if isinstance(disk, (int,float)) and disk > 90: alerts.append(f"⚠️DISCO:{disk}%")
            lines.append(f"{icon} {s.get('name')} | Estado:{s.get('status')} | CPU:{cpu}% | RAM:{mem}% | Disco:{disk}% {' '.join(alerts)}")
        return "\n".join(lines) or "Sin datos de servidores."

    def _mock(self):
        return {
            "servers": [
                {"name":"Servidor-APP-01","status":"up","is_healthy":True,"cpu_usage":45,"memory_usage":67,"disk_usage":55},
                {"name":"Servidor-DB-01","status":"up","is_healthy":True,"cpu_usage":23,"memory_usage":81,"disk_usage":70},
                {"name":"Servidor-WEB-01","status":"degraded","is_healthy":False,"cpu_usage":89,"memory_usage":92,"disk_usage":45},
            ],
            "last_updated": datetime.utcnow().isoformat(),
            "_demo": True,
        }


server_monitor_service = ServerMonitorService()


