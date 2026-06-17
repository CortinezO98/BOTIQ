from __future__ import annotations

from typing import Any, Dict, Optional


class RoutingPolicyService:
    """
    Enrutamiento liviano sin IA para reducir consumo de Vertex.

    Objetivo:
    - Evitar llamar RAG/embeddings/Gemini cuando la consulta es de ofimática general.
    - Usar RAG solo para conocimiento interno/procedimientos/documentos corporativos.
    - Activar web/cache para soporte técnico general cuando no haya FAQ aprobada.
    """

    GENERAL_TECH_KEYWORDS = {
        "excel", "word", "powerpoint", "outlook", "teams", "onedrive", "sharepoint",
        "office", "microsoft", "windows", "chrome", "edge", "firefox", "navegador",
        "impresora", "imprimir", "printer", "pdf", "adobe", "acrobat", "archivo",
        "formula", "fórmula", "suma", "sumar", "celda", "columna", "fila",
        "certificado", "ssl", "tls", "cache", "caché", "cookies", "driver",
    }

    INTERNAL_KNOWLEDGE_KEYWORDS = {
        "procedimiento", "manual", "instructivo", "documentación", "documentacion",
        "base de conocimiento", "afc", "bancolombia", "canje", "tigo", "pgd",
        "firewall regional", "firewall_regionales", "portal interno", "adminrea",
        "aranda", "vpn iq", "iq-online", "servidor", "server", "ip", "url",
        "aplicativo", "aplicación", "aplicacion", "producción", "produccion",
        "ambiente", "certificado interno", "bd", "base de datos",
    }

    URL_HINTS = {"http://", "https://", "www.", ".com", ".net", ".co", ".local", ".intranet"}

    def classify_message(
        self,
        message: str,
        profile: Optional[str] = None,
        has_url: bool = False,
        has_ip: bool = False,
        matrix_found: bool = False,
        case_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        msg = (message or "").lower()
        general_hits = sorted([k for k in self.GENERAL_TECH_KEYWORDS if k in msg])
        internal_hits = sorted([k for k in self.INTERNAL_KNOWLEDGE_KEYWORDS if k in msg])
        has_url_hint = has_url or any(h in msg for h in self.URL_HINTS)
        internal_signal = bool(has_ip or matrix_found or internal_hits or has_url_hint)

        is_general_tech = bool(general_hits) and not internal_signal

        # Empleado con Excel/Word/Outlook/etc. debe evitar RAG interno si no hay señales internas.
        if profile == "employee" and is_general_tech:
            return {
                "intent_family": "general_tech",
                "use_faq": True,
                "use_web_cache": True,
                "use_rag": False,
                "use_status": False,
                "use_web_fallback": True,
                "reason": "Consulta técnica general de herramienta; se evita RAG interno para no traer documentos irrelevantes.",
                "general_hits": general_hits,
                "internal_hits": internal_hits,
            }

        # Soporte también puede preguntar por Excel/Windows general; usar cache/web antes que RAG si no hay contexto interno.
        if profile == "support_engineer" and is_general_tech:
            return {
                "intent_family": "general_tech_support",
                "use_faq": True,
                "use_web_cache": True,
                "use_rag": False,
                "use_status": False,
                "use_web_fallback": True,
                "reason": "Consulta general de soporte; se evita RAG si no hay señales internas.",
                "general_hits": general_hits,
                "internal_hits": internal_hits,
            }

        return {
            "intent_family": "internal_or_mixed",
            "use_faq": True,
            "use_web_cache": True,
            "use_rag": True,
            "use_status": bool(internal_signal or matrix_found or has_url or has_ip),
            "use_web_fallback": True,
            "reason": "Consulta interna/mixta o sin clasificación general; se permite RAG.",
            "general_hits": general_hits,
            "internal_hits": internal_hits,
        }


routing_policy_service = RoutingPolicyService()
