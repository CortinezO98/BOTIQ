"""Rutas del dashboard de métricas — solo Admin."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.dashboard import DashboardMetrics, MetricsSummary

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(
    days: int = Query(default=30, ge=1, le=365),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    total_conv = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= period_start)
    )).scalar() or 0

    total_msg = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= period_start)
    )).scalar() or 0

    escalations = (await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.escalated_to_aranda == True,
            Conversation.created_at >= period_start,
        )
    )).scalar() or 0

    tokens = (await db.execute(
        select(func.sum(Message.tokens_used)).where(Message.created_at >= period_start)
    )).scalar() or 0

    avg_time = (await db.execute(
        select(func.avg(Message.response_time_ms)).where(
            Message.created_at >= period_start, Message.response_time_ms.isnot(None)
        )
    )).scalar() or 0

    return DashboardMetrics(
        total_conversations=total_conv,
        total_messages=total_msg,
        avg_response_time_ms=avg_time,
        total_tokens_used=tokens,
        escalations_to_aranda=escalations,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/summary", response_model=MetricsSummary)
async def get_summary(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    today_c = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= today))).scalar() or 0
    week_c  = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago))).scalar() or 0

    top_mod = (await db.execute(
        select(Conversation.module, func.count(Conversation.id).label("c"))
        .where(Conversation.created_at >= week_ago)
        .group_by(Conversation.module).order_by(desc("c")).limit(1)
    )).first()

    return MetricsSummary(
        today_conversations=today_c,
        week_conversations=week_c,
        top_module=top_mod[0].value if top_mod else "employee",
        support_gap_count=0,
    )
