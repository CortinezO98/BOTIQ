"""
Módulo de validación de servidores.
Consume la API del tablero de servidores y usa Gemini para análisis contextual.
"""

import httpx
from typing import Dict, List, Optional
from datetime import datetime

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service

SERVER_ANALYSIS_PROMPT = """
Eres un especialista en infraestructura de TI.
Analiza el siguiente estado de los servidores corporativos y proporciona:

1. Un resumen ejecutivo del estado general
2. Servidores con problemas críticos (si los hay)
3. Advertencias de rendimiento
4. Recomendaciones de acción inmediata

Estado actual de los servidores:
{server_data}

Responde en español de forma clara y estructurada.
Si todo está bien, indícalo positivamente.
Si hay problemas, sé específico sobre qué servidor y qué tipo de problema.
"""


class ServerMonitorService:
    """
    Servicio de monitoreo de servidores.
    Solo el bot accede internamente a la API — los usuarios ven el análisis en lenguaje natural.
    """

    def __init__(self):
        self.api_url = settings.SERVER_DASHBOARD_API_URL
        self.api_key = settings.SERVER_DASHBOARD_API_KEY

    async def fetch_server_status(self) -> Dict:
        """
        Consulta el tablero de servidores via API.
        """
        if not self.api_url:
            return self._mock_server_data()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.api_url}/servers/status",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def analyze_and_respond(
        self,
        user_query: str,
        image_analysis: Optional[str] = None,
    ) -> Dict:
        """
        Obtiene el estado de servidores y genera respuesta con Gemini.
        """
        # Obtener datos de servidores (solo el bot accede a esto)
        server_data = await self.fetch_server_status()

        # Formatear datos para el prompt
        server_summary = self._format_server_data(server_data)

        # Si hay análisis de imagen, incluirlo
        if image_analysis:
            server_summary += f"\n\nCaptura del usuario: {image_analysis}"

        system_prompt = SERVER_ANALYSIS_PROMPT.format(server_data=server_summary)

        result = await gemini_text_service.generate(
            prompt=user_query,
            system_instruction=system_prompt,
            temperature=0.1,
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "raw_server_data": server_data,
            "queried_at": datetime.utcnow().isoformat(),
        }

    def _format_server_data(self, data: Dict) -> str:
        """Formatea los datos del tablero para el prompt de Gemini."""
        servers = data.get("servers", [])
        if not servers:
            return "No se pudo obtener información de los servidores."

        lines = []
        for server in servers:
            status_icon = "✅" if server.get("is_healthy") else "❌"
            lines.append(
                f"{status_icon} Servidor: {server.get('name', 'N/A')}\n"
                f"   Estado: {server.get('status', 'N/A')}\n"
                f"   CPU: {server.get('cpu_usage', 'N/A')}%\n"
                f"   Memoria: {server.get('memory_usage', 'N/A')}%\n"
                f"   Disco: {server.get('disk_usage', 'N/A')}%\n"
            )
        return "\n".join(lines)

    def _mock_server_data(self) -> Dict:
        """Datos de prueba cuando no hay API configurada."""
        return {
            "servers": [
                {
                    "name": "Servidor-APP-01",
                    "status": "up",
                    "is_healthy": True,
                    "cpu_usage": 45.2,
                    "memory_usage": 67.8,
                    "disk_usage": 55.0,
                },
                {
                    "name": "Servidor-DB-01",
                    "status": "up",
                    "is_healthy": True,
                    "cpu_usage": 23.1,
                    "memory_usage": 81.5,
                    "disk_usage": 70.2,
                },
            ],
            "last_updated": datetime.utcnow().isoformat(),
        }


server_monitor_service = ServerMonitorService()
