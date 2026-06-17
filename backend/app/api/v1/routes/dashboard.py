from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone
from typing import List
from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.faq import FAQ
from app.models.knowledge_gap import KnowledgeGap
from app.schemas.dashboard import (
    DashboardMetrics, MetricsSummary, ConvByModule, ConvByDay,
    TopFAQ, TokenConsumption, KnowledgeGapItem, EscalationRate,
)

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(days: int = Query(30, ge=1, le=365), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    tc = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= start))).scalar() or 0
    tm = (await db.execute(select(func.count(Message.id)).where(Message.created_at >= start))).scalar() or 0
    esc = (await db.execute(select(func.count(Conversation.id)).where(Conversation.escalated_to_aranda == True, Conversation.created_at >= start))).scalar() or 0
    tok = (await db.execute(select(func.sum(Message.tokens_used)).where(Message.created_at >= start))).scalar() or 0
    avg = (await db.execute(select(func.avg(Message.response_time_ms)).where(Message.created_at >= start, Message.response_time_ms.isnot(None)))).scalar() or 0
    gaps = (await db.execute(select(func.count(KnowledgeGap.id)).where(KnowledgeGap.status == "open"))).scalar() or 0
    return DashboardMetrics(total_conversations=tc, total_messages=tm, avg_response_time_ms=round(avg, 1),
                            total_tokens_used=float(tok), escalations_to_aranda=esc,
                            open_knowledge_gaps=gaps, period_start=start, period_end=end)


@router.get("/summary", response_model=MetricsSummary)
async def get_summary(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    tc = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= today))).scalar() or 0
    wc = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago))).scalar() or 0
    top = (await db.execute(select(Conversation.module, func.count(Conversation.id).label("c")).where(Conversation.created_at >= week_ago).group_by(Conversation.module).order_by(desc("c")).limit(1))).first()
    gc = (await db.execute(select(func.count(KnowledgeGap.id)).where(KnowledgeGap.status == "open"))).scalar() or 0
    return MetricsSummary(today_conversations=tc, week_conversations=wc, top_module=top[0].value if top else "employee", support_gap_count=gc)


@router.get("/conversations-by-module", response_model=List[ConvByModule])
async def conv_by_module(days: int = Query(30), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    r = await db.execute(select(Conversation.module, func.count(Conversation.id).label("count")).where(Conversation.created_at >= start).group_by(Conversation.module).order_by(desc("count")))
    return [ConvByModule(module=row.module.value, count=row.count) for row in r]


@router.get("/conversations-by-day", response_model=List[ConvByDay])
async def conv_by_day(days: int = Query(30), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    r = await db.execute(select(func.date(Conversation.created_at).label("date"), func.count(Conversation.id).label("count")).where(Conversation.created_at >= start).group_by(func.date(Conversation.created_at)).order_by("date"))
    return [ConvByDay(date=str(row.date), count=row.count) for row in r]


@router.get("/top-faqs", response_model=List[TopFAQ])
async def top_faqs(limit: int = Query(10), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(FAQ).where(FAQ.is_active == True, FAQ.hit_count > 0).order_by(desc(FAQ.hit_count)).limit(limit))
    return [TopFAQ(question=f.question, hits=f.hit_count, category=f.category or "") for f in r.scalars()]


@router.get("/token-consumption", response_model=List[TokenConsumption])
async def token_cons(days: int = Query(30), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    r = await db.execute(select(func.date(Message.created_at).label("date"), func.sum(Message.tokens_used).label("tokens")).where(Message.created_at >= start, Message.tokens_used.isnot(None)).group_by(func.date(Message.created_at)).order_by("date"))
    return [TokenConsumption(date=str(row.date), tokens=int(row.tokens or 0)) for row in r]


@router.get("/knowledge-gaps", response_model=List[KnowledgeGapItem])
async def knowledge_gaps(limit: int = Query(20), status: str = Query("open"), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(KnowledgeGap).where(KnowledgeGap.status == status).order_by(desc(KnowledgeGap.frequency)).limit(limit))
    return [KnowledgeGapItem(id=str(g.id), query=g.query, module=g.module, frequency=g.frequency, avg_confidence=g.avg_confidence, last_seen=g.last_seen, status=g.status) for g in r.scalars()]


@router.get("/escalation-rate", response_model=EscalationRate)
async def escalation_rate(days: int = Query(30), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    total = (await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= start))).scalar() or 0
    esc = (await db.execute(select(func.count(Conversation.id)).where(Conversation.escalated_to_aranda == True, Conversation.created_at >= start))).scalar() or 0
    return EscalationRate(total=total, escalated=esc, rate_pct=round((esc/total*100), 2) if total > 0 else 0.0)


