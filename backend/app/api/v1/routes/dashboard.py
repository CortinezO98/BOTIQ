"""
Dashboard de métricas — solo accesible para administradores.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType
from app.schemas.dashboard import DashboardMetrics, MetricsSummary

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna métricas del chatbot para el período indicado.
    Solo accesible para administradores.
    """
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    # Total conversaciones
    conv_count = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.created_at >= period_start
        )
    )
    total_conversations = conv_count.scalar() or 0

    # Total mensajes
    msg_count = await db.execute(
        select(func.count(Message.id)).where(
            Message.created_at >= period_start
        )
    )
    total_messages = msg_count.scalar() or 0

    # Escalaciones a Aranda
    escalations = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.escalated_to_aranda == True,
            Conversation.created_at >= period_start,
        )
    )
    total_escalations = escalations.scalar() or 0

    # Tokens consumidos
    tokens_result = await db.execute(
        select(func.sum(Message.tokens_used)).where(
            Message.created_at >= period_start
        )
    )
    total_tokens = tokens_result.scalar() or 0

    # Tiempo promedio de respuesta
    avg_time_result = await db.execute(
        select(func.avg(Message.response_time_ms)).where(
            Message.created_at >= period_start,
            Message.response_time_ms.isnot(None),
        )
    )
    avg_response_time = avg_time_result.scalar() or 0

    return DashboardMetrics(
        total_conversations=total_conversations,
        total_messages=total_messages,
        avg_response_time_ms=avg_response_time,
        total_tokens_used=total_tokens,
        escalations_to_aranda=total_escalations,
        most_frequent_queries=[],   # Implementar análisis semántico
        server_metrics=[],          # Implementar desde server_logs
        support_gaps=[],            # Implementar análisis de confianza RAG
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/summary", response_model=MetricsSummary)
async def get_summary(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Resumen rápido del día y la semana."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    today_conv = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= today)
    )
    week_conv = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago)
    )

    # Módulo más usado esta semana
    top_module_result = await db.execute(
        select(Conversation.module, func.count(Conversation.id).label("count"))
        .where(Conversation.created_at >= week_ago)
        .group_by(Conversation.module)
        .order_by(desc("count"))
        .limit(1)
    )
    top_module_row = top_module_result.first()
    top_module = top_module_row[0].value if top_module_row else "employee"

    return MetricsSummary(
        today_conversations=today_conv.scalar() or 0,
        week_conversations=week_conv.scalar() or 0,
        top_module=top_module,
        most_reported_server=None,
        support_gap_count=0,
    )
