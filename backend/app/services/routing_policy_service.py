from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


class RoutingPolicyService:
    """
    Enrutamiento liviano sin IA para reducir consumo de Vertex.

    Objetivo:
    - Evitar RAG/embeddings/Gemini cuando la consulta es de ofimática o tecnología general.
    - Usar RAG solo cuando existan señales internas/corporativas reales.
    - Permitir fallback web/IA general cuando no haya FAQ ni conocimiento interno.
    - Mantener contexto cuando el usuario envía seguimientos cortos como:
      "GUIAME", "continúa", "no funcionó", "paso a paso", etc.
    """

    GENERAL_TECH_KEYWORDS: Set[str] = {
        # Microsoft / ofimática
        "excel",
        "word",
        "powerpoint",
        "outlook",
        "teams",
        "onedrive",
        "sharepoint",
        "office",
        "microsoft",

        # Sistema operativo / navegador
        "windows",
        "chrome",
        "edge",
        "firefox",
        "navegador",
        "browser",

        # Impresión / periféricos
        "impresora",
        "impresoras",
        "imprimir",
        "impresion",
        "impresión",
        "printer",
        "driver",
        "controlador",
        "cola de impresion",
        "cola de impresión",

        # Archivos / PDF
        "pdf",
        "adobe",
        "acrobat",
        "archivo",
        "documento",
        "carpeta",
        "descarga",
        "descargar",

        # Excel / fórmulas
        "formula",
        "fórmula",
        "formulas",
        "fórmulas",
        "suma",
        "sumar",
        "celda",
        "columna",
        "fila",
        "tabla dinamica",
        "tabla dinámica",

        # Certificados / navegador general
        "certificado",
        "ssl",
        "tls",
        "cache",
        "caché",
        "cookies",
        "historial",
    }

    INTERNAL_KNOWLEDGE_KEYWORDS: Set[str] = {
        # Conocimiento interno / procedimientos
        "procedimiento",
        "manual",
        "instructivo",
        "documentación",
        "documentacion",
        "base de conocimiento",
        "política interna",
        "politica interna",
        "lineamiento",
        "protocolo",

        # Herramientas / portales internos conocidos
        "adminrea",
        "aranda",
        "iq-online",
        "portal interno",
        "intranet",
        "aplicativo interno",

        # Aplicativos/campañas/servicios internos mencionados
        "afc",
        "bancolombia",
        "canje",
        "tigo",
        "pgd",
        "firewall regional",
        "firewall_regionales",

        # Infraestructura
        "servidor",
        "servidores",
        "server",
        "ip",
        "url",
        "dns",
        "dominio",
        "puerto",
        "vpn iq",
        "vpn corporativa",
        "producción",
        "produccion",
        "ambiente",
        "ambiente productivo",
        "base de datos",
        "bd",
        "certificado interno",
    }

    URL_HINTS: Set[str] = {
        "http://",
        "https://",
        "www.",
        ".com",
        ".net",
        ".co",
        ".org",
        ".local",
        ".intranet",
    }

    FOLLOW_UP_KEYWORDS: Set[str] = {
        "guiame",
        "guíame",
        "orientame",
        "oriéntame",
        "paso a paso",
        "continua",
        "continúa",
        "sigue",
        "siguiente",
        "que hago",
        "qué hago",
        "ayudame",
        "ayúdame",
        "no funciono",
        "no funcionó",
        "sigue igual",
        "aun no",
        "aún no",
        "todavia no",
        "todavía no",
        "y ahora",
        "ahora que",
        "ahora qué",
    }

    GENERAL_CASE_TYPES: Set[str] = {
        "printer_issue",
        "computer_issue",
        "file_issue",
        "general_support",
    }

    INTERNAL_CASE_TYPES: Set[str] = {
        "access_issue",
        "app_down",
        "server_status",
        "procedure",
    }

    SHORT_FOLLOW_UP_MAX_CHARS = 45

    def classify_message(
        self,
        message: str,
        profile: Optional[str] = None,
        has_url: bool = False,
        has_ip: bool = False,
        matrix_found: bool = False,
        case_type: Optional[str] = None,
        previous_intent_family: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clasifica una consulta para decidir qué fuentes usar.

        Retorna banderas para la cadena de respuesta:
        - use_faq
        - use_web_cache
        - use_rag
        - use_status
        - use_web_fallback
        - use_general_ai_fallback
        """

        msg = self._normalize(message)
        profile = (profile or "").strip().lower()
        case_type = (case_type or "").strip().lower()
        previous_intent_family = (previous_intent_family or "").strip().lower()

        general_hits = self._find_keyword_hits(msg, self.GENERAL_TECH_KEYWORDS)
        internal_hits = self._find_keyword_hits(msg, self.INTERNAL_KNOWLEDGE_KEYWORDS)

        has_url_hint = has_url or self._has_url_hint(msg)
        is_follow_up = self._is_short_follow_up(msg)

        internal_signal = bool(
            has_ip
            or matrix_found
            or has_url_hint
            or internal_hits
            or case_type in self.INTERNAL_CASE_TYPES
        )

        general_signal = bool(
            general_hits
            or case_type in self.GENERAL_CASE_TYPES
        )

        # Caso importante:
        # Si el usuario dice "GUIAME", "continúa", "no funcionó", etc.,
        # y la conversación anterior ya era de tecnología general,
        # se conserva ese enrutamiento para no perder contexto.
        if is_follow_up and previous_intent_family in {
            "general_tech",
            "general_tech_support",
        }:
            return self._general_response(
                intent_family=previous_intent_family,
                profile=profile,
                reason=(
                    "Mensaje corto de seguimiento. Se conserva el contexto anterior "
                    "de tecnología general para evitar perder el hilo conversacional."
                ),
                general_hits=general_hits,
                internal_hits=internal_hits,
                is_follow_up=True,
                internal_signal=internal_signal,
                has_url_hint=has_url_hint,
            )

        # Si hay una señal interna fuerte, se permite RAG y validación de estado.
        # Ejemplo: URL interna, IP, aplicativo en matriz, Aranda, servidor, portal interno.
        if internal_signal:
            return self._internal_response(
                reason=(
                    "Consulta con señales internas/corporativas. Se permite RAG, "
                    "matriz de aplicaciones y validación de estado."
                ),
                general_hits=general_hits,
                internal_hits=internal_hits,
                is_follow_up=is_follow_up,
                internal_signal=internal_signal,
                has_url_hint=has_url_hint,
            )

        # Consulta general de tecnología/ofimática sin señales internas.
        if general_signal and profile in {"employee", "support_engineer", "admin", ""}:
            intent_family = (
                "general_tech_support"
                if profile in {"support_engineer", "admin"}
                else "general_tech"
            )

            return self._general_response(
                intent_family=intent_family,
                profile=profile,
                reason=(
                    "Consulta de tecnología/ofimática general sin señales internas. "
                    "Se evita RAG interno para no traer documentación corporativa irrelevante."
                ),
                general_hits=general_hits,
                internal_hits=internal_hits,
                is_follow_up=is_follow_up,
                internal_signal=internal_signal,
                has_url_hint=has_url_hint,
            )

        # Si no hay señales claras, se trata como mixta/interna para no perder
        # la posibilidad de buscar en la base corporativa.
        return self._internal_response(
            reason=(
                "Consulta sin clasificación general suficiente o potencialmente mixta. "
                "Se permite RAG para validar si existe conocimiento corporativo."
            ),
            general_hits=general_hits,
            internal_hits=internal_hits,
            is_follow_up=is_follow_up,
            internal_signal=internal_signal,
            has_url_hint=has_url_hint,
        )

    def _general_response(
        self,
        intent_family: str,
        profile: str,
        reason: str,
        general_hits: List[str],
        internal_hits: List[str],
        is_follow_up: bool,
        internal_signal: bool,
        has_url_hint: bool,
    ) -> Dict[str, Any]:
        return {
            "intent_family": intent_family,
            "use_faq": True,
            "use_web_cache": True,
            "use_rag": False,
            "use_status": False,
            "use_web_fallback": True,
            "use_general_ai_fallback": True,
            "should_register_knowledge_gap": False,
            "reason": reason,
            "profile": profile or None,
            "general_hits": general_hits,
            "internal_hits": internal_hits,
            "is_follow_up": is_follow_up,
            "internal_signal": internal_signal,
            "has_url_hint": has_url_hint,
        }

    def _internal_response(
        self,
        reason: str,
        general_hits: List[str],
        internal_hits: List[str],
        is_follow_up: bool,
        internal_signal: bool,
        has_url_hint: bool,
    ) -> Dict[str, Any]:
        return {
            "intent_family": "internal_or_mixed",
            "use_faq": True,
            "use_web_cache": True,
            "use_rag": True,
            "use_status": bool(internal_signal or has_url_hint),
            "use_web_fallback": True,
            "use_general_ai_fallback": False,
            "should_register_knowledge_gap": True,
            "reason": reason,
            "general_hits": general_hits,
            "internal_hits": internal_hits,
            "is_follow_up": is_follow_up,
            "internal_signal": internal_signal,
            "has_url_hint": has_url_hint,
        }

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _has_url_hint(self, msg: str) -> bool:
        return any(hint in msg for hint in self.URL_HINTS)

    def _is_short_follow_up(self, msg: str) -> bool:
        if not msg:
            return False

        if len(msg) <= self.SHORT_FOLLOW_UP_MAX_CHARS:
            if any(keyword in msg for keyword in self.FOLLOW_UP_KEYWORDS):
                return True

            # Frases muy cortas sin sustancia técnica suelen ser continuación.
            if len(msg.split()) <= 4 and not self._find_keyword_hits(msg, self.INTERNAL_KNOWLEDGE_KEYWORDS):
                return True

        return any(keyword in msg for keyword in self.FOLLOW_UP_KEYWORDS)

    def _find_keyword_hits(self, msg: str, keywords: Set[str]) -> List[str]:
        """
        Busca coincidencias con más cuidado que `keyword in msg`.

        - Para frases con espacios, permite búsqueda directa.
        - Para palabras sueltas, exige límites de palabra para reducir falsos positivos.
        """
        hits: List[str] = []

        for keyword in keywords:
            key = keyword.strip().lower()
            if not key:
                continue

            if " " in key:
                if key in msg:
                    hits.append(key)
                continue

            pattern = r"(?<![a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_])" + re.escape(key) + r"(?![a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_])"
            if re.search(pattern, msg, flags=re.IGNORECASE):
                hits.append(key)

        return sorted(set(hits))


routing_policy_service = RoutingPolicyService()