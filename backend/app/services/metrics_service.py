"""
Servicio de métricas agregadas para el dashboard de BOTIQ.
Centraliza todas las consultas analíticas sobre conversaciones, mensajes y servidores.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from app.models.conversation import Conversation, Message, ModuleType, MessageRole
from app.models.server_log import ServerLog
from app.models.faq import FAQ


class MetricsService:

    async def get_conversations_by_module(
        self,
        db: AsyncSession,
        start: datetime,
        end: datetime,
    ) -> List[Dict]:
        """Distribución de conversaciones por módulo en el período."""
        result = await db.execute(
            select(
                Conversation.module,
                func.count(Conversation.id).label("count")
            )
            .where(
                Conversation.created_at >= start,
                Conversation.created_at <= end,
            )
            .group_by(Conversation.module)
            .order_by(desc("count"))
        )
        return [{"module": row.module.value, "count": row.count} for row in result]

    async def get_daily_conversations(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> List[Dict]:
        """Conversaciones por día para el gráfico de línea."""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(
                func.date(Conversation.created_at).label("date"),
                func.count(Conversation.id).label("count"),
            )
            .where(Conversation.created_at >= start)
            .group_by(func.date(Conversation.created_at))
            .order_by("date")
        )
        return [{"date": str(row.date), "count": row.count} for row in result]

    async def get_avg_response_time_by_module(
        self,
        db: AsyncSession,
        start: datetime,
        end: datetime,
    ) -> List[Dict]:
        """Tiempo promedio de respuesta por módulo."""
        result = await db.execute(
            select(
                Conversation.module,
                func.avg(Message.response_time_ms).label("avg_ms"),
            )
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.created_at >= start,
                Conversation.created_at <= end,
                Message.role == MessageRole.ASSISTANT,
                Message.response_time_ms.isnot(None),
            )
            .group_by(Conversation.module)
        )
        return [
            {"module": row.module.value, "avg_response_ms": round(row.avg_ms or 0, 1)}
            for row in result
        ]

    async def get_top_faqs(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> List[Dict]:
        """FAQs más consultadas."""
        result = await db.execute(
            select(FAQ)
            .where(FAQ.is_active == True, FAQ.hit_count > 0)
            .order_by(desc(FAQ.hit_count))
            .limit(limit)
        )
        faqs = result.scalars().all()
        return [
            {"question": faq.question, "hits": faq.hit_count, "category": faq.category}
            for faq in faqs
        ]

    async def get_server_incidents(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> List[Dict]:
        """Servidores con más incidentes en el período."""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(
                ServerLog.server_name,
                func.count(ServerLog.id).label("incident_count"),
                func.avg(ServerLog.memory_usage).label("avg_memory"),
                func.avg(ServerLog.cpu_usage).label("avg_cpu"),
                func.max(ServerLog.queried_at).label("last_seen"),
            )
            .where(
                ServerLog.queried_at >= start,
                ServerLog.is_healthy == False,
            )
            .group_by(ServerLog.server_name)
            .order_by(desc("incident_count"))
            .limit(10)
        )
        return [
            {
                "server_name": row.server_name,
                "incident_count": row.incident_count,
                "avg_memory": round(row.avg_memory or 0, 1),
                "avg_cpu": round(row.avg_cpu or 0, 1),
                "last_incident": str(row.last_seen),
            }
            for row in result
        ]

    async def get_escalation_rate(
        self,
        db: AsyncSession,
        start: datetime,
        end: datetime,
    ) -> Dict:
        """Tasa de escalación a Aranda."""
        total_result = await db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.created_at >= start, Conversation.created_at <= end)
        )
        total = total_result.scalar() or 0

        escalated_result = await db.execute(
            select(func.count(Conversation.id))
            .where(
                Conversation.created_at >= start,
                Conversation.created_at <= end,
                Conversation.escalated_to_aranda == True,
            )
        )
        escalated = escalated_result.scalar() or 0

        rate = (escalated / total * 100) if total > 0 else 0
        return {
            "total_conversations": total,
            "escalated": escalated,
            "escalation_rate_pct": round(rate, 2),
        }

    async def get_tokens_consumption(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> List[Dict]:
        """Consumo de tokens de Vertex AI por día."""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(
                func.date(Message.created_at).label("date"),
                func.sum(Message.tokens_used).label("tokens"),
            )
            .where(
                Message.created_at >= start,
                Message.tokens_used.isnot(None),
            )
            .group_by(func.date(Message.created_at))
            .order_by("date")
        )
        return [{"date": str(row.date), "tokens": int(row.tokens or 0)} for row in result]


metrics_service = MetricsService()
