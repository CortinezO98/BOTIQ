"""Módulo de validación de servidores."""
import httpx
from typing import Dict, Optional
from datetime import datetime

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service

SYSTEM_PROMPT = """Eres un especialista en infraestructura de TI.
Analiza el estado de los servidores corporativos:

{server_data}

Proporciona:
1. Resumen ejecutivo del estado general
2. Servidores con problemas críticos
3. Advertencias de rendimiento
4. Recomendaciones de acción inmediata

Responde en español. Si todo está bien, indícalo positivamente.
"""


class ServerMonitorService:

    async def fetch_server_status(self) -> Dict:
        if not settings.SERVER_DASHBOARD_API_URL:
            return self._mock_data()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.SERVER_DASHBOARD_API_URL}/servers/status",
                    headers={"Authorization": f"Bearer {settings.SERVER_DASHBOARD_API_KEY}"},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"Server API error: {e}")
            return self._mock_data()

    async def analyze_and_respond(self, user_query: str, image_analysis: Optional[str] = None) -> Dict:
        server_data = await self.fetch_server_status()
        summary = self._format(server_data)
        if image_analysis:
            summary += f"\n\nCaptura del usuario: {image_analysis}"

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
        lines = []
        for s in servers:
            icon = "✅" if s.get("is_healthy") else "❌"
            lines.append(f"{icon} {s.get('name')} | Estado: {s.get('status')} | CPU: {s.get('cpu_usage')}% | RAM: {s.get('memory_usage')}%")
        return "\n".join(lines) if lines else "Sin datos de servidores."

    def _mock_data(self) -> Dict:
        return {
            "servers": [
                {"name": "Servidor-APP-01", "status": "up", "is_healthy": True, "cpu_usage": 45, "memory_usage": 67, "disk_usage": 55},
                {"name": "Servidor-DB-01",  "status": "up", "is_healthy": True, "cpu_usage": 23, "memory_usage": 81, "disk_usage": 70},
            ],
            "last_updated": datetime.utcnow().isoformat(),
            "note": "Datos de demostración — configura SERVER_DASHBOARD_API_URL para datos reales",
        }


server_monitor_service = ServerMonitorService()
