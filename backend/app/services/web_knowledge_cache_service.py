from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re
import uuid

from rapidfuzz import fuzz
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.faq import FAQ
from app.models.web_knowledge_cache import WebKnowledgeCache
from app.services.vertex.gemini_text_service import gemini_text_service


class WebKnowledgeCacheService:
    """
    Memoria revisable de conocimiento web.

    Esta capa evita que BOTIQ dependa de internet cada vez:
    - Busca primero conocimiento aprobado.
    - Registra sugerencias web como pending.
    - Permite aprobarlas como FAQ.
    """

    def normalize_question(self, question: str) -> str:
        q = (question or "").lower().strip()
        q = re.sub(r"https?://\S+", " url ", q)
        q = re.sub(r"www\.\S+", " url ", q)
        q = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", " ip ", q)
        q = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q[:500]

    def infer_category(self, question: str) -> str:
        q = (question or "").lower()
        if any(k in q for k in ["excel", "word", "office", "archivo", "pdf", "adobe"]):
            return "Ofimática y archivos"
        if any(k in q for k in ["outlook", "correo", "email", "teams", "onedrive", "sharepoint"]):
            return "Microsoft 365"
        if any(k in q for k in ["impresora", "imprimir", "printer"]):
            return "Impresoras"
        if any(k in q for k in ["chrome", "edge", "firefox", "navegador", "certificado", "ssl", "tls"]):
            return "Navegadores y certificados"
        if any(k in q for k in ["vpn", "red", "wifi", "firewall", "conexión", "conexion"]):
            return "Red y conectividad"
        if any(k in q for k in ["windows", "pc", "computador", "equipo", "pantalla"]):
            return "Equipo de cómputo"
        if any(k in q for k in ["500", "501", "502", "503", "504", "http"]):
            return "Errores HTTP"
        return "Soporte técnico general"

    def infer_tags(self, question: str, category: Optional[str] = None) -> List[str]:
        q = (question or "").lower()
        tags: List[str] = []
        candidates = [
            "excel", "word", "outlook", "teams", "onedrive", "sharepoint", "windows",
            "chrome", "edge", "firefox", "impresora", "pdf", "adobe", "vpn", "ssl",
            "tls", "certificado", "error 500", "error 501", "error 502", "error 503",
            "error 504", "archivo dañado", "no abre", "bloqueo",
        ]
        for candidate in candidates:
            if candidate in q:
                tags.append(candidate)
        if category:
            tags.append(category.lower())
        return list(dict.fromkeys(tags))[:12]

    async def find_approved(self, db: AsyncSession, question: str, min_score: int = 72) -> Optional[Dict[str, Any]]:
        normalized = self.normalize_question(question)
        if not normalized:
            return None

        rows = (
            await db.execute(
                select(WebKnowledgeCache)
                .where(
                    WebKnowledgeCache.status == "approved",
                    WebKnowledgeCache.expires_at > datetime.now(timezone.utc),
                )
                .order_by(WebKnowledgeCache.usage_count.desc(), WebKnowledgeCache.created_at.desc())
                .limit(200)
            )
        ).scalars().all()

        best = None
        best_score = 0
        for row in rows:
            score = max(
                fuzz.token_set_ratio(normalized, row.normalized_question or ""),
                fuzz.partial_ratio(normalized, row.normalized_question or ""),
                fuzz.token_set_ratio(normalized, row.question.lower()),
            )
            if score > best_score:
                best = row
                best_score = score

        if best and best_score >= min_score:
            best.usage_count = (best.usage_count or 0) + 1
            await db.flush()
            return {
                "id": str(best.id),
                "question": best.question,
                "answer": best.answer,
                "category": best.category,
                "sources": best.sources or [],
                "score": best_score,
                "source": "web_knowledge_cache_approved",
            }

        return None

    async def daily_web_search_count(self, db: AsyncSession) -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.count(WebKnowledgeCache.id)).where(
                WebKnowledgeCache.web_search_used == True,
                WebKnowledgeCache.created_at >= start,
            )
        )
        return int(result.scalar() or 0)

    async def can_use_web_today(self, db: AsyncSession) -> tuple[bool, int, int]:
        limit = int(getattr(settings, "WEB_SEARCH_DAILY_LIMIT", 100) or 100)
        used = await self.daily_web_search_count(db)
        return used < limit, used, limit

    async def build_answer_from_web(
        self,
        question: str,
        web_context: str,
        image_analysis: Optional[str] = None,
        profile: str = "employee",
    ) -> Dict[str, Any]:
        system_instruction = (
            "Eres BOTIQ, asistente corporativo de soporte TI. "
            "Debes sintetizar una respuesta segura usando referencias públicas y el contexto interno disponible. "
            "No inventes políticas internas, URLs internas, estados de servidores ni credenciales. "
            "Si la solución requiere privilegios de administrador, indícalo. "
            "Responde en español con pasos claros, advertencias y cuándo escalar."
        )
        prompt = (
            f"Consulta del usuario: {question}\n\n"
            f"Referencias públicas consultadas:\n{web_context}\n\n"
            "Genera una respuesta útil y breve para mesa de ayuda:\n"
            "1. Causa probable.\n"
            "2. Pasos seguros para el usuario.\n"
            "3. Cuándo escalar a soporte/Aranda.\n"
            "4. Resumen corto para futura FAQ.\n"
            "Máximo 450 palabras.\n"
        )
        if image_analysis:
            prompt += f"\nContexto de imagen/captura enviada por el usuario:\n{image_analysis}\n"

        result = await gemini_text_service.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.15,
            model=settings.VERTEX_FAST_MODEL,
            max_output_tokens=settings.WEB_ANSWER_MAX_OUTPUT_TOKENS,
        )
        return result

    async def register_pending(
        self,
        db: AsyncSession,
        question: str,
        answer: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        created_by: Optional[uuid.UUID] = None,
        confidence: float = 0.65,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> WebKnowledgeCache:
        normalized = self.normalize_question(question)
        category = category or self.infer_category(question)
        tags = tags or self.infer_tags(question, category)

        # Si existe pendiente similar, actualiza frecuencia/contexto en vez de duplicar.
        existing = (
            await db.execute(
                select(WebKnowledgeCache).where(
                    WebKnowledgeCache.status == "pending",
                    WebKnowledgeCache.normalized_question == normalized,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.answer = answer
            existing.sources = sources or existing.sources
            existing.category = category
            existing.tags = tags
            existing.confidence = confidence
            existing.usage_count = (existing.usage_count or 0) + 1
            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing

        row = WebKnowledgeCache(
            question=question[:2000],
            normalized_question=normalized,
            answer=answer,
            sources=sources or [],
            category=category,
            tags=tags,
            confidence=confidence,
            status="pending",
            created_by=created_by,
            usage_count=1,
            web_search_used=True,
        )
        db.add(row)
        await db.flush()
        return row

    async def list_items(
        self,
        db: AsyncSession,
        status: str = "pending",
        q: str = "",
        limit: int = 100,
    ) -> List[WebKnowledgeCache]:
        stmt = (
            select(WebKnowledgeCache)
            .where(WebKnowledgeCache.status == status)
            .order_by(WebKnowledgeCache.created_at.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).scalars().all()

        if q:
            qn = q.lower().strip()
            rows = [
                r for r in rows
                if qn in (r.question or "").lower()
                or qn in (r.answer or "").lower()
                or qn in (r.category or "").lower()
                or qn in " ".join(r.tags or []).lower()
            ]
        return rows

    async def approve_as_faq(
        self,
        db: AsyncSession,
        item: WebKnowledgeCache,
        approved_by: uuid.UUID,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        create_faq: bool = True,
    ) -> WebKnowledgeCache:
        item.question = question or item.question
        item.normalized_question = self.normalize_question(item.question)
        item.answer = answer or item.answer
        item.category = category if category is not None else item.category
        item.tags = tags if tags is not None else item.tags
        item.status = "approved"
        item.approved_by = approved_by
        item.approved_at = datetime.now(timezone.utc)
        item.updated_at = datetime.now(timezone.utc)

        if create_faq and not item.faq_id:
            faq = FAQ(
                question=item.question,
                answer=item.answer,
                category=item.category,
                tags=item.tags or [],
                is_active=True,
            )
            db.add(faq)
            await db.flush()
            item.faq_id = faq.id

        await db.flush()
        return item

    async def reject(
        self,
        db: AsyncSession,
        item: WebKnowledgeCache,
        rejected_by: uuid.UUID,
        reason: Optional[str] = None,
    ) -> WebKnowledgeCache:
        item.status = "rejected"
        item.rejected_by = rejected_by
        item.rejected_at = datetime.now(timezone.utc)
        item.rejection_reason = reason
        item.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return item


web_knowledge_cache_service = WebKnowledgeCacheService()


