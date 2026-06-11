"""
Módulo de empleados: FAQ + Gemini Pro para preguntas frecuentes corporativas.
Flujo: FAQ match → Gemini con contexto → Escalada a Aranda (última instancia)
"""

from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.faq import FAQ
from app.services.vertex.gemini_text_service import gemini_text_service

EMPLOYEE_SYSTEM_PROMPT = """
Eres BOTIQ, el asistente virtual corporativo de la empresa.
Tu función es ayudar a los empleados con preguntas frecuentes sobre:
- Problemas de acceso a portales y sistemas internos
- Errores en aplicaciones de oficina (Word, Excel, Outlook, etc.)
- Procedimientos internos de TI
- Solicitudes de soporte básico

Reglas importantes:
1. Responde siempre en español de forma clara y concisa
2. Si tienes una respuesta en la base de FAQ, úsala como guía principal
3. Si no puedes resolver el problema, indica al usuario que será escalado a Aranda (sistema de tickets)
4. No inventes procedimientos que no existan
5. Sé amable y profesional en todo momento
6. Si el usuario sube una imagen de error, analízala y da una solución específica
"""

ESCALATION_PROMPT = """
No he podido encontrar una solución específica para tu consulta en mi base de conocimiento.
Te recomiendo crear un ticket en **Aranda** para que un ingeniero de soporte te pueda ayudar personalmente.

¿Hay algo más en lo que pueda ayudarte mientras tanto?
"""


class EmployeeBotService:

    async def get_faq_answer(self, query: str, db: AsyncSession) -> Optional[Dict]:
        """
        Busca una respuesta en la base de FAQ.
        Usa búsqueda por palabras clave simple.
        """
        # Búsqueda básica por similitud de texto
        words = query.lower().split()
        results = await db.execute(
            select(FAQ).where(FAQ.is_active == True).limit(20)
        )
        faqs = results.scalars().all()

        best_match = None
        best_score = 0

        for faq in faqs:
            question_lower = faq.question.lower()
            score = sum(1 for word in words if word in question_lower)
            if score > best_score and score >= 2:
                best_score = score
                best_match = faq

        if best_match:
            # Incrementar contador de uso
            best_match.hit_count += 1
            await db.commit()
            return {
                "faq_id": str(best_match.id),
                "question": best_match.question,
                "answer": best_match.answer,
                "category": best_match.category,
            }

        return None

    async def generate_response(
        self,
        user_message: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        faq_context: Optional[Dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict:
        """
        Genera respuesta para un empleado usando FAQ + Gemini.
        """
        should_escalate = False

        # Enriquecer el prompt con contexto FAQ e imagen
        context_parts = []

        if faq_context:
            context_parts.append(
                f"Pregunta similar en FAQ: {faq_context['question']}\n"
                f"Respuesta sugerida: {faq_context['answer']}"
            )

        if image_analysis:
            context_parts.append(f"Análisis de imagen del usuario: {image_analysis}")

        context = "\n\n".join(context_parts)
        prompt = f"{context}\n\nConsulta del empleado: {user_message}" if context else user_message

        result = await gemini_text_service.generate(
            prompt=prompt,
            system_instruction=EMPLOYEE_SYSTEM_PROMPT,
            history=history,
            temperature=0.3,
        )

        # Detectar si Gemini indica que no puede resolver
        no_solution_keywords = [
            "no tengo información", "no puedo ayudarte con eso",
            "contacta a soporte", "crea un ticket", "escalar"
        ]
        response_lower = result["text"].lower()
        if any(kw in response_lower for kw in no_solution_keywords):
            should_escalate = True

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "escalated_to_aranda": should_escalate,
            "faq_used": faq_context is not None,
        }


employee_bot_service = EmployeeBotService()
