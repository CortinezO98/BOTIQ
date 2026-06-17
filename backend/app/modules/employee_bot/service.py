from typing import Dict, List, Optional

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.faq import FAQ
from app.services.vertex.gemini_text_service import gemini_text_service

SYSTEM = """Eres BOTIQ, el asistente virtual corporativo de IQ.

Alcance permitido:
- Accesos a portales, URLs y aplicativos corporativos
- Errores de aplicaciones como Word, Excel, Outlook, Teams, VPN y sistemas internos
- Procedimientos internos de TI
- Disponibilidad de aplicativos/servidores cuando BOTIQ reciba información interna
- Soporte técnico básico y orientación antes de crear ticket

Reglas obligatorias:
1. Responde siempre en español, claro y conciso.
2. No respondas temas ajenos al negocio o fuera del soporte corporativo de IQ.
3. Si el usuario reporta que no puede entrar a una URL y no dio URL/IP, pídele la URL o IP.
4. Si tienes una FAQ relevante, úsala como base.
5. Antes de recomendar ticket, intenta agotar validaciones básicas: URL/IP, error exacto, navegador/VPN/credenciales/cache y estado del servicio si existe.
6. No inventes estados de servidores ni resultados de APIs; usa únicamente la información interna entregada en el prompt.
7. Si no hay información suficiente, indícalo y pide los datos faltantes.
"""


class EmployeeBotService:
    async def get_faq_answer(self, query: str, db: AsyncSession) -> Optional[Dict]:
        result = await db.execute(
            select(FAQ)
            .where(FAQ.is_active == True)
            .order_by(FAQ.hit_count.desc(), FAQ.created_at.desc())
            .limit(100)
        )
        faqs = result.scalars().all()

        query_norm = query.lower().strip()
        best = None
        best_score = 0

        for faq in faqs:
            question_score = fuzz.token_set_ratio(query_norm, faq.question.lower())
            answer_score = fuzz.token_set_ratio(query_norm, faq.answer.lower()[:300])

            tag_score = 0
            if faq.tags:
                tag_score = max(fuzz.token_set_ratio(query_norm, tag.lower()) for tag in faq.tags if tag)

            category_score = fuzz.token_set_ratio(query_norm, faq.category.lower()) if faq.category else 0
            score = max(question_score, answer_score * 0.75, tag_score, category_score)

            if score > best_score:
                best_score = score
                best = faq

        if best and best_score >= 65:
            best.hit_count += 1
            await db.commit()
            return {
                "question": best.question,
                "answer": best.answer,
                "category": best.category,
                "score": round(best_score, 2),
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
        parts = []

        if faq_context:
            parts.append(
                "FAQ relacionada:\n"
                f"P: {faq_context['question']}\n"
                f"R: {faq_context['answer']}\n"
                f"Confianza FAQ: {faq_context.get('score', 'N/A')}"
            )

        if image_analysis:
            parts.append(f"Análisis de imagen: {image_analysis}")

        context = "\n\n".join(parts)
        prompt = f"{context}\n\nConsulta del empleado: {user_message}" if context else user_message

        result = await gemini_text_service.generate(
            prompt=prompt,
            system_instruction=SYSTEM,
            history=history,
            temperature=0.25,
            model=settings.VERTEX_FAST_MODEL,
        )

        text_lower = result["text"].lower()
        escalate = any(
            kw in text_lower
            for kw in [
                "no hay información suficiente",
                "no tengo información",
                "no encontré información",
                "crear ticket",
                "aranda",
                "escalar",
            ]
        )

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "escalated_to_aranda": escalate,
            "faq_used": faq_context is not None,
        }


employee_bot_service = EmployeeBotService()


