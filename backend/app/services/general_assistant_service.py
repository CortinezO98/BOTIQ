from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service


GENERAL_SYSTEM_INSTRUCTION = """
Eres BOTIQ, asistente virtual corporativo de IQ.

Vas a responder una consulta de ofimática o tecnología general, por ejemplo:
Excel, Word, Outlook, Teams, Windows, navegadores, impresoras, PDF, certificados,
VPN, red básica, archivos, periféricos o errores comunes de herramientas.

Contexto importante:
- No hay una FAQ interna aplicable.
- No hay un documento suficiente en la base de conocimiento corporativa.
- La búsqueda web no estuvo disponible o no entregó una respuesta útil.
- Por eso debes orientar con conocimiento general y público de la herramienta.

Reglas estrictas:
1. Responde únicamente con orientación general de la herramienta o tecnología mencionada.
2. No inventes aplicativos internos de IQ, URLs internas, IPs, servidores, estados,
   políticas internas, procedimientos de Aranda, AdminREA, portales propios ni datos
   que no estén en el contexto.
3. Si el caso depende de una configuración interna de IQ, dilo claramente y recomienda
   escalar a soporte con la evidencia necesaria.
4. No digas frases largas como "Como BOTIQ..." o "De acuerdo con mi conocimiento...".
   Empieza directamente con la orientación.
5. Da pasos concretos, breves y accionables.
6. Si el usuario pide "guíame", "paso a paso", "continúa", "qué hago" o algo similar,
   debes continuar con el último problema técnico tratado en el historial.
7. Si hay una captura o análisis de imagen, úsalo para orientar la respuesta, pero no
   afirmes datos internos que no estén visibles.
8. Máximo 6 pasos.
9. Cierra con una recomendación breve sobre cuándo escalar a soporte.
10. Aclara que es una guía general, no un procedimiento interno validado por IQ.
"""


FOLLOW_UP_PATTERNS = {
    "guiame",
    "guíame",
    "orientame",
    "oriéntame",
    "paso a paso",
    "continua",
    "continúa",
    "sigue",
    "que hago",
    "qué hago",
    "ayudame",
    "ayúdame",
    "no funciono",
    "no funcionó",
    "sigue igual",
    "y ahora",
    "ahora que",
    "ahora qué",
}


INTERNAL_RISK_KEYWORDS = {
    "aranda",
    "adminrea",
    "iq",
    "portal interno",
    "servidor interno",
    "ip interna",
    "base de datos interna",
    "vpn corporativa",
    "directorio activo",
    "active directory",
    "ldap",
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _is_short_follow_up(question: str) -> bool:
    normalized = _normalize_text(question)
    if not normalized:
        return False

    if len(normalized) <= 45:
        return True

    return any(pattern in normalized for pattern in FOLLOW_UP_PATTERNS)


def _extract_recent_user_context(history: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """
    Recupera el último mensaje útil del usuario para que frases cortas como
    "GUIAME", "continúa" o "no funcionó" no pierdan el contexto.
    """
    if not history:
        return None

    for item in reversed(history):
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or "").strip()

        if role == "user" and content and not _is_short_follow_up(content):
            return content[:500]

    return None


def _contains_internal_dependency(question: str, image_analysis: Optional[str] = None) -> bool:
    text = f"{question or ''} {image_analysis or ''}".lower()
    return any(keyword in text for keyword in INTERNAL_RISK_KEYWORDS)


def _clean_response(text: str) -> str:
    """
    Limpieza defensiva para evitar respuestas con prefijos largos o frases
    que hacen parecer que BOTIQ está citando política interna cuando no lo está.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # Evita arranques repetitivos o poco útiles.
    cleaned = re.sub(r"^(como botiq[,:\s]*)", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(
        r"^(de acuerdo con mi conocimiento[,:\s]*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Evita múltiples saltos de línea excesivos.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned


def _fallback_general_message(question: str) -> str:
    """
    Respuesta segura cuando Gemini falla o devuelve una salida vacía.
    """
    return (
        "No pude generar una guía completa en este momento, pero puedes iniciar con estas validaciones generales:\n\n"
        "1. Confirma el error exacto que aparece en pantalla.\n"
        "2. Reinicia la aplicación o el equipo si el problema es local.\n"
        "3. Verifica conexión, permisos, cableado o red según el caso.\n"
        "4. Prueba nuevamente con otro archivo, navegador o usuario si aplica.\n"
        "5. Toma una captura del error y registra fecha, hora y usuario afectado.\n"
        "6. Si el problema continúa, escálalo a soporte con esa evidencia.\n\n"
        "Esta es una orientación general, no un procedimiento interno validado por IQ."
    )


class GeneralAssistantService:
    """
    Último eslabón de la cadena de respaldo.

    Orden recomendado del flujo:
    1. FAQ interna.
    2. RAG corporativo.
    3. Conocimiento web aprobado.
    4. Búsqueda web controlada.
    5. Este servicio: Gemini con conocimiento general, sin fuente interna.

    Este servicio NO debe responder sobre políticas internas, aplicativos internos,
    URLs internas, estados de servidores ni procedimientos corporativos específicos.
    """

    async def build_general_answer(
        self,
        question: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        question = (question or "").strip()

        previous_context = _extract_recent_user_context(history)

        prompt_parts: List[str] = []

        if previous_context and _is_short_follow_up(question):
            prompt_parts.append(
                "Contexto anterior del usuario:\n"
                f"{previous_context}"
            )
            prompt_parts.append(
                "Mensaje actual del usuario:\n"
                f"{question}"
            )
            prompt_parts.append(
                "Instrucción:\n"
                "El usuario está pidiendo continuidad o guía sobre el contexto anterior. "
                "Responde manteniendo ese problema como tema principal."
            )
        else:
            prompt_parts.append(f"Pregunta del usuario:\n{question}")

        if image_analysis:
            prompt_parts.append(
                "Contexto de imagen o captura enviada por el usuario:\n"
                f"{image_analysis}"
            )

        if _contains_internal_dependency(question, image_analysis):
            prompt_parts.append(
                "Advertencia:\n"
                "La consulta puede depender de configuración interna de IQ. "
                "No inventes datos internos. Si no es posible dar pasos generales, "
                "recomienda escalar a soporte con evidencia."
            )

        prompt_parts.append(
            "Formato obligatorio de respuesta:\n"
            "- Empieza directo con la solución.\n"
            "- Máximo 6 pasos numerados.\n"
            "- Usa lenguaje claro y práctico.\n"
            "- No inventes información interna.\n"
            "- Termina indicando cuándo escalar a soporte.\n"
            "- Aclara que es una guía general, no un procedimiento interno validado por IQ."
        )

        prompt = "\n\n".join(prompt_parts)

        try:
            result = await gemini_text_service.generate(
                prompt=prompt,
                system_instruction=GENERAL_SYSTEM_INSTRUCTION,
                history=history,
                temperature=0.2,
                model=settings.VERTEX_FAST_MODEL,
                max_output_tokens=settings.GENERAL_AI_ANSWER_MAX_OUTPUT_TOKENS,
            )

            text = _clean_response(str(result.get("text") or ""))

            if not text:
                text = _fallback_general_message(question)

            result["text"] = text
            result["source"] = "general_ai_fallback"
            result["is_internal_procedure"] = False
            result["requires_admin_review"] = True

            return result

        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "text": _fallback_general_message(question),
                "error": str(exc),
                "tokens_used": 0,
                "response_time_ms": 0,
                "source": "general_ai_fallback_error",
                "is_internal_procedure": False,
                "requires_admin_review": True,
            }


general_assistant_service = GeneralAssistantService()