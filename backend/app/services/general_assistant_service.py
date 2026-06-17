from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.vertex.gemini_text_service import gemini_text_service

GENERAL_SYSTEM_INSTRUCTION = (
    "Eres BOTIQ, asistente corporativo de IQ. Vas a responder una pregunta de ofimática o "
    "tecnología GENERAL (Excel, Word, Outlook, Windows, navegadores, impresoras, certificados, etc.) "
    "para la cual NO hay FAQ interna, NO hay documento en la base de conocimiento corporativa, y "
    "la búsqueda web no estuvo disponible o no dio resultados.\n\n"
    "Reglas estrictas:\n"
    "1. Responde solo con conocimiento general y público de la herramienta mencionada. "
    "NUNCA inventes nombres de aplicativos internos de IQ, URLs internas, IPs, estados de "
    "servidores, políticas internas, ni procedimientos de Aranda/AdminREA/portales propios — "
    "de eso no tienes información y no debes simular que sí.\n"
    "2. Si la pregunta en realidad depende de cómo IQ configuró algo internamente (no de cómo "
    "funciona la herramienta en general), dilo explícitamente y recomienda escalar a soporte "
    "en vez de adivinar.\n"
    "3. Sé claro en que esta es orientación general de la herramienta, no un procedimiento "
    "validado por IQ.\n"
    "4. Da pasos concretos y breves. Indica si el paso a paso puede variar según la versión "
    "del programa.\n"
    "5. Máximo 4-5 pasos o un párrafo corto."
)


class GeneralAssistantService:
    """
    Último eslabón de la cadena de respaldo, solo para preguntas de
    ofimática/tecnología general (ver routing_policy_service.is_general_tech).

    Orden completo: FAQ -> RAG interno -> conocimiento web aprobado ->
    búsqueda web + Gemini -> ESTE servicio (Gemini con su propio
    conocimiento, sin ninguna fuente externa).
    """

    async def build_general_answer(
        self,
        question: str,
        image_analysis: Optional[str] = None,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        prompt = f"Pregunta del usuario:\n{question}"
        if image_analysis:
            prompt += f"\n\nContexto de imagen/captura enviada por el usuario:\n{image_analysis}"

        result = await gemini_text_service.generate(
            prompt=prompt,
            system_instruction=GENERAL_SYSTEM_INSTRUCTION,
            history=history,
            temperature=0.2,
            model=settings.VERTEX_FAST_MODEL,
            max_output_tokens=settings.GENERAL_AI_ANSWER_MAX_OUTPUT_TOKENS,
        )
        return result


general_assistant_service = GeneralAssistantService()