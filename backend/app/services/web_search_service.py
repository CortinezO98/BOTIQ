from typing import Any, Dict, List

import httpx

from app.core.config import settings


class WebSearchService:
    """
    Búsqueda web controlada para soporte técnico general.

    Uso dentro del flujo BOTIQ:
    1. Primero se consulta FAQ interna.
    2. Luego base de conocimiento / RAG.
    3. Luego matriz de aplicaciones y estado de aplicativos/servidores.
    4. Solo si no hay respuesta interna suficiente, se permite búsqueda web.

    Seguridad:
    - No busca URLs internas, IPs privadas, dominios internos ni nombres sensibles.
    - No debe reemplazar la base de conocimiento corporativa.
    - No inventa estados de servidores internos.
    """

    PRIVATE_HINTS = [
        "10.", "192.168.",
        "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
        "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
        ".local", ".lan", ".intranet", "intranet", "iq-online", "adminrea", " rea ", "vpn iq",
    ]

    GENERAL_TECH_KEYWORDS = [
        "excel", "word", "outlook", "teams", "windows", "office", "onedrive", "sharepoint",
        "impresora", "printer", "archivo", "archivo dañado", "no abre", "bloqueado", "bloqueo",
        "navegador", "chrome", "edge", "firefox", "certificado", "ssl", "tls", "vpn",
        "error 400", "error 401", "error 403", "error 404", "error 408", "error 429",
        "error 500", "error 501", "error 502", "error 503", "error 504",
        "http 400", "http 401", "http 403", "http 404", "http 500", "http 501", "http 502", "http 503", "http 504",
    ]

    def is_enabled(self) -> bool:
        return bool(settings.WEB_SEARCH_ENABLED and settings.WEB_SEARCH_API_URL and settings.WEB_SEARCH_API_KEY)

    def is_allowed_query(self, query: str) -> bool:
        q = f" {query or ''} ".lower()
        if not q.strip():
            return False

        if any(hint in q for hint in self.PRIVATE_HINTS):
            return False

        return any(keyword in q for keyword in self.GENERAL_TECH_KEYWORDS)

    async def search(self, query: str) -> Dict[str, Any]:
        if not settings.WEB_SEARCH_ENABLED:
            return {"enabled": False, "used": False, "reason": "WEB_SEARCH_ENABLED=false", "results": []}

        if not self.is_allowed_query(query):
            return {
                "enabled": True,
                "used": False,
                "reason": "Consulta no permitida para búsqueda web por contener posible información interna o no ser soporte técnico general.",
                "results": [],
            }

        if not self.is_enabled():
            return {
                "enabled": True,
                "used": False,
                "reason": "Búsqueda web no configurada. Define WEB_SEARCH_API_URL, WEB_SEARCH_API_KEY y WEB_SEARCH_CX si usas Google Custom Search.",
                "results": [],
            }

        provider = (settings.WEB_SEARCH_PROVIDER or "google_custom_search").lower().strip()
        if provider == "google_custom_search":
            return await self._google_custom_search(query)

        return await self._generic_search(query)

    async def _google_custom_search(self, query: str) -> Dict[str, Any]:
        params = {
            "q": query,
            "key": settings.WEB_SEARCH_API_KEY,
            "cx": settings.WEB_SEARCH_CX,
            "num": max(1, min(int(settings.WEB_SEARCH_MAX_RESULTS or 5), 10)),
            "lr": "lang_es",
        }
        if not settings.WEB_SEARCH_CX:
            return {"enabled": True, "used": False, "reason": "WEB_SEARCH_CX no configurado.", "results": []}

        try:
            async with httpx.AsyncClient(timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS) as client:
                response = await client.get(settings.WEB_SEARCH_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            items = data.get("items") or []
            results = [
                {
                    "title": item.get("title") or "",
                    "snippet": item.get("snippet") or "",
                    "link": item.get("link") or "",
                    "source": "google_custom_search",
                }
                for item in items[: settings.WEB_SEARCH_MAX_RESULTS]
            ]
            return {"enabled": True, "used": bool(results), "reason": None if results else "Sin resultados web.", "results": results}
        except Exception as exc:  # noqa: BLE001
            return {"enabled": True, "used": False, "reason": f"No fue posible consultar internet: {exc}", "results": []}

    async def _generic_search(self, query: str) -> Dict[str, Any]:
        """Proveedor genérico compatible con APIs que reciban ?q= y retornen items/results."""
        headers = {"Authorization": f"Bearer {settings.WEB_SEARCH_API_KEY}"} if settings.WEB_SEARCH_API_KEY else {}
        try:
            async with httpx.AsyncClient(timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS) as client:
                response = await client.get(settings.WEB_SEARCH_API_URL, params={"q": query}, headers=headers)
                response.raise_for_status()
                data = response.json()

            raw_results = data.get("items") or data.get("results") or []
            results: List[Dict[str, str]] = []
            for item in raw_results[: settings.WEB_SEARCH_MAX_RESULTS]:
                results.append(
                    {
                        "title": item.get("title") or item.get("name") or "",
                        "snippet": item.get("snippet") or item.get("description") or item.get("content") or "",
                        "link": item.get("link") or item.get("url") or "",
                        "source": "generic_web_search",
                    }
                )
            return {"enabled": True, "used": bool(results), "reason": None if results else "Sin resultados web.", "results": results}
        except Exception as exc:  # noqa: BLE001
            return {"enabled": True, "used": False, "reason": f"No fue posible consultar internet: {exc}", "results": []}

    def format_for_prompt(self, web_result: Dict[str, Any]) -> str:
        results = web_result.get("results") or []
        if not results:
            return ""

        lines = []
        for idx, result in enumerate(results[: settings.WEB_SEARCH_MAX_RESULTS], start=1):
            title = result.get("title") or "Resultado web"
            snippet = result.get("snippet") or ""
            link = result.get("link") or ""
            lines.append(f"[{idx}] {title}\nResumen: {snippet}\nURL pública: {link}")
        return "\n\n".join(lines)


web_search_service = WebSearchService()


