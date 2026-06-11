"""Módulo Employee Bot — FAQ + Gemini."""
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.faq import FAQ
from app.services.vertex.gemini_text_service import gemini_text_service

SYSTEM_PROMPT = """Eres BOTIQ, el asistente virtual corporativo.
Ayudas a los empleados con:
- Problemas de acceso a portales y sistemas internos
- Errores en aplicaciones de oficina (Word, Excel, Outlook, etc.)
- Procedimientos internos de TI
- Soporte técnico básico

Reglas:
1. Responde siempre en español, de forma clara y concisa
2. Si tienes una FAQ relevante, úsala como base
3. Si no puedes resolver el problema, indica que se escalará a Aranda
4. Sé amable y profesional
"""


class EmployeeBotService:

    async def get_faq_answer(self, query: str, db: AsyncSession) -> Optional[Dict]:
        result = await db.execute(select(FAQ).where(FAQ.is_active == True).limit(50))
        faqs = result.scalars().all()
        words = set(query.lower().split())
        best, best_score = None, 0
        for faq in faqs:
            score = sum(1 for w in words if w in faq.question.lower())
            if score > best_score and score >= 2:
                best_score, best = score, faq
        if best:
            best.hit_count += 1
            await db.commit()
            return {"question": best.question, "answer": best.answer, "category": best.category}
        return None

    async def generate_response(
        self,
        user_message: str,
        image_analysis: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        faq_context: Optional[Dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict:
        context_parts = []
        if faq_context:
            context_parts.append(f"FAQ relacionada:\nP: {faq_context['question']}\nR: {faq_context['answer']}")
        if image_analysis:
            context_parts.append(f"Análisis de imagen: {image_analysis}")

        context = "\n\n".join(context_parts)
        prompt = f"{context}\n\nConsulta: {user_message}" if context else user_message

        result = await gemini_text_service.generate(
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            history=history,
            temperature=0.3,
        )

        escalate_keywords = ["no tengo información", "contacta a soporte", "crea un ticket", "aranda"]
        escalated = any(kw in result["text"].lower() for kw in escalate_keywords)

        return {
            "text": result["text"],
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "escalated_to_aranda": escalated,
            "faq_used": faq_context is not None,
        }


employee_bot_service = EmployeeBotService()
