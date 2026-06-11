"""Servicio de métricas para el dashboard."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from app.models.conversation import Conversation, Message, MessageRole
from app.models.server_log import ServerLog
from app.models.faq import FAQ


class MetricsService:

    async def get_conversations_by_module(self, db: AsyncSession, start: datetime, end: datetime) -> List[Dict]:
        result = await db.execute(
            select(Conversation.module, func.count(Conversation.id).label("count"))
            .where(Conversation.created_at >= start, Conversation.created_at <= end)
            .group_by(Conversation.module).order_by(desc("count"))
        )
        return [{"module": row.module.value, "count": row.count} for row in result]

    async def get_daily_conversations(self, db: AsyncSession, days: int = 30) -> List[Dict]:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(func.date(Conversation.created_at).label("date"), func.count(Conversation.id).label("count"))
            .where(Conversation.created_at >= start)
            .group_by(func.date(Conversation.created_at)).order_by("date")
        )
        return [{"date": str(row.date), "count": row.count} for row in result]

    async def get_top_faqs(self, db: AsyncSession, limit: int = 10) -> List[Dict]:
        result = await db.execute(
            select(FAQ).where(FAQ.is_active == True, FAQ.hit_count > 0)
            .order_by(desc(FAQ.hit_count)).limit(limit)
        )
        return [{"question": f.question, "hits": f.hit_count, "category": f.category} for f in result.scalars()]

    async def get_tokens_consumption(self, db: AsyncSession, days: int = 30) -> List[Dict]:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(func.date(Message.created_at).label("date"), func.sum(Message.tokens_used).label("tokens"))
            .where(Message.created_at >= start, Message.tokens_used.isnot(None))
            .group_by(func.date(Message.created_at)).order_by("date")
        )
        return [{"date": str(row.date), "tokens": int(row.tokens or 0)} for row in result]


metrics_service = MetricsService()
