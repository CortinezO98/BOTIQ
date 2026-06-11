"""
Dashboard de métricas BOTIQ — todos los endpoints conectados a datos reales.
Solo accesibles para rol ADMIN.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timedelta, timezone
from typing import List

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType
from app.models.faq import FAQ
from app.models.knowledge_gap import KnowledgeGap
from app.schemas.dashboard import (
    DashboardMetrics, MetricsSummary,
    ConvByModule, ConvByDay, TopFAQ,
    KnowledgeGapItem, TokenConsumption, EscalationRate,
)

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics,
            summary="Métricas generales del período")
async def get_metrics(
    days: int = Query(default=30, ge=1, le=365),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    total_conv = (await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.created_at >= start)
    )).scalar() or 0

    total_msg = (await db.execute(
        select(func.count(Message.id))
        .where(Message.created_at >= start)
    )).scalar() or 0

    escalations = (await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.escalated_to_aranda == True, Conversation.created_at >= start)
    )).scalar() or 0

    tokens = (await db.execute(
        select(func.sum(Message.tokens_used)).where(Message.created_at >= start)
    )).scalar() or 0

    avg_time = (await db.execute(
        select(func.avg(Message.response_time_ms))
        .where(Message.created_at >= start, Message.response_time_ms.isnot(None))
    )).scalar() or 0

    knowledge_gaps = (await db.execute(
        select(func.count(KnowledgeGap.id)).where(KnowledgeGap.status == "open")
    )).scalar() or 0

    return DashboardMetrics(
        total_conversations=total_conv,
        total_messages=total_msg,
        avg_response_time_ms=round(avg_time, 1),
        total_tokens_used=float(tokens),
        escalations_to_aranda=escalations,
        open_knowledge_gaps=knowledge_gaps,
        period_start=start,
        period_end=end,
    )


@router.get("/summary", response_model=MetricsSummary,
            summary="Resumen rápido hoy y esta semana")
async def get_summary(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    today_c = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= today)
    )).scalar() or 0

    week_c = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago)
    )).scalar() or 0

    top_mod = (await db.execute(
        select(Conversation.module, func.count(Conversation.id).label("c"))
        .where(Conversation.created_at >= week_ago)
        .group_by(Conversation.module).order_by(desc("c")).limit(1)
    )).first()

    gap_count = (await db.execute(
        select(func.count(KnowledgeGap.id)).where(KnowledgeGap.status == "open")
    )).scalar() or 0

    return MetricsSummary(
        today_conversations=today_c,
        week_conversations=week_c,
        top_module=top_mod[0].value if top_mod else "employee",
        support_gap_count=gap_count,
    )


@router.get("/conversations-by-module", response_model=List[ConvByModule],
            summary="Conversaciones agrupadas por módulo")
async def conversations_by_module(
    days: int = Query(default=30),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Conversation.module, func.count(Conversation.id).label("count"))
        .where(Conversation.created_at >= start)
        .group_by(Conversation.module).order_by(desc("count"))
    )
    return [ConvByModule(module=row.module.value, count=row.count) for row in result]


@router.get("/conversations-by-day", response_model=List[ConvByDay],
            summary="Conversaciones por día (para gráfico de línea)")
async def conversations_by_day(
    days: int = Query(default=30),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
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
    return [ConvByDay(date=str(row.date), count=row.count) for row in result]


@router.get("/top-faqs", response_model=List[TopFAQ],
            summary="FAQs más consultadas")
async def top_faqs(
    limit: int = Query(default=10, ge=1, le=50),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FAQ).where(FAQ.is_active == True, FAQ.hit_count > 0)
        .order_by(desc(FAQ.hit_count)).limit(limit)
    )
    faqs = result.scalars().all()
    return [TopFAQ(question=f.question, hits=f.hit_count, category=f.category or "") for f in faqs]


@router.get("/token-consumption", response_model=List[TokenConsumption],
            summary="Consumo de tokens Vertex AI por día")
async def token_consumption(
    days: int = Query(default=30),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Message.created_at).label("date"),
            func.sum(Message.tokens_used).label("tokens"),
        )
        .where(Message.created_at >= start, Message.tokens_used.isnot(None))
        .group_by(func.date(Message.created_at)).order_by("date")
    )
    return [TokenConsumption(date=str(row.date), tokens=int(row.tokens or 0)) for row in result]


@router.get("/knowledge-gaps", response_model=List[KnowledgeGapItem],
            summary="Brechas de conocimiento detectadas")
async def knowledge_gaps(
    limit: int = Query(default=20),
    status: str = Query(default="open"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeGap)
        .where(KnowledgeGap.status == status)
        .order_by(desc(KnowledgeGap.frequency))
        .limit(limit)
    )
    gaps = result.scalars().all()
    return [
        KnowledgeGapItem(
            id=str(g.id), query=g.query, module=g.module,
            frequency=g.frequency, avg_confidence=g.avg_confidence,
            last_seen=g.last_seen, status=g.status,
        )
        for g in gaps
    ]


@router.get("/escalation-rate", response_model=EscalationRate,
            summary="Tasa de escalaciones a Aranda")
async def escalation_rate(
    days: int = Query(default=30),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    start = datetime.now(timezone.utc) - timedelta(days=days)

    total = (await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= start)
    )).scalar() or 0

    escalated = (await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.escalated_to_aranda == True, Conversation.created_at >= start)
    )).scalar() or 0

    rate = round((escalated / total * 100), 2) if total > 0 else 0.0
    return EscalationRate(total=total, escalated=escalated, rate_pct=rate)
