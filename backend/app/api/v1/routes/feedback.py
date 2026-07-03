"""
Endpoints de feedback y satisfacción — BOTIQ v1.4.0

POST /api/v1/chat/message/{message_id}/feedback
    Registra 👍 o 👎 sobre un mensaje del asistente.
    Si es 👎, incrementa o crea un knowledge_gap para ese query.

POST /api/v1/chat/session/{session_id}/satisfaction
    Registra la encuesta de satisfacción al cerrar la conversación.
    Guarda score (1=Resolvió, 2=Parcial, 3=No resolvió), comentario y flag resolved_by_bot.

GET  /api/v1/dashboard/feedback/summary
    Resumen de feedback para el panel admin: total 👍, total 👎, mensajes peor calificados.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.conversation import Conversation, Message, MessageRole
from app.models.knowledge_gap import KnowledgeGap
from app.models.message_feedback import MessageFeedback
from app.models.user import User

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(up|down)$", description="'up' o 'down'")
    comment: Optional[str] = Field(None, max_length=500)


class SatisfactionRequest(BaseModel):
    score: int = Field(..., ge=1, le=3, description="1=Resolvió mi problema, 2=Parcialmente, 3=No resolvió")
    comment: Optional[str] = Field(None, max_length=500)


# ── POST /chat/message/{message_id}/feedback ───────────────────────────────────

@router.post("/message/{message_id}/feedback")
async def submit_feedback(
    message_id: UUID,
    data: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra 👍 o 👎 sobre una respuesta del bot.

    Si el rating es 'down':
    - Se crea o incrementa un knowledge_gap con el contenido del mensaje.
    - El gap queda marcado como 'open' para revisión admin.
    """
    # Verificar que el mensaje existe y es del asistente
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.role != MessageRole.ASSISTANT:
        raise HTTPException(status_code=400,
                            detail="Solo se puede calificar mensajes del asistente")

    # Verificar que el usuario tiene acceso a esa conversación
    conv = await db.get(Conversation, msg.conversation_id)
    if not conv or str(conv.user_id) != str(current_user.id):
        if current_user.role.value not in ("admin", "support_engineer"):
            raise HTTPException(status_code=403, detail="Sin acceso a esta conversación")

    # Upsert: si ya existe feedback de este usuario para este mensaje, actualiza
    existing = (await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.message_id == message_id,
            MessageFeedback.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.rating = data.rating
        existing.comment = data.comment
        feedback = existing
    else:
        feedback = MessageFeedback(
            message_id=message_id,
            conversation_id=msg.conversation_id,
            user_id=current_user.id,
            rating=data.rating,
            comment=data.comment,
        )
        db.add(feedback)

    # Si es 👎, registrar o incrementar knowledge_gap
    if data.rating == "down":
        # Usar el primer trozo del mensaje como query representativo
        query_text = (msg.content or "")[:200].strip()
        if query_text:
            gap = (await db.execute(
                select(KnowledgeGap).where(KnowledgeGap.query == query_text)
            )).scalar_one_or_none()

            if gap:
                gap.frequency = (gap.frequency or 1) + 1
                gap.last_seen = datetime.now(timezone.utc)
            else:
                db.add(KnowledgeGap(
                    query=query_text,
                    module=conv.module.value if conv else "unknown",
                    user_role=current_user.role.value,
                    frequency=1,
                    avg_confidence=0.0,
                    last_seen=datetime.now(timezone.utc),
                    status="open",
                    suggested_document="Revisión manual por feedback negativo del usuario.",
                ))

    await db.commit()
    await db.refresh(feedback)

    return {
        "feedback_id": str(feedback.id),
        "rating": feedback.rating,
        "message": "Feedback registrado. Gracias por tu calificación.",
    }


# ── POST /chat/session/{session_id}/satisfaction ──────────────────────────────

@router.post("/session/{session_id}/satisfaction")
async def submit_satisfaction(
    session_id: str,
    data: SatisfactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra la encuesta de satisfacción al cerrar la conversación.
    Score: 1 = Resolvió | 2 = Parcialmente | 3 = No resolvió.
    """
    conv = (await db.execute(
        select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conv.satisfaction_score is not None:
        raise HTTPException(status_code=400, detail="Esta conversación ya fue calificada")

    conv.satisfaction_score = data.score
    conv.satisfaction_comment = data.comment
    conv.resolved_by_bot = data.score == 1
    conv.satisfaction_given_at = datetime.now(timezone.utc)

    await db.commit()

    labels = {1: "Resolvió el problema", 2: "Parcialmente resuelto", 3: "No resolvió"}
    return {
        "satisfaction_score": data.score,
        "label": labels.get(data.score, ""),
        "resolved_by_bot": conv.resolved_by_bot,
        "message": "Gracias por tu calificación. Tu feedback ayuda a mejorar BOTIQ.",
    }


# ── GET /dashboard/feedback/summary ──────────────────────────────────────────

@router.get("/feedback/summary")
async def feedback_summary(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Resumen de feedback para el panel admin.
    Incluye conteo total de 👍/👎 y los mensajes peor calificados.
    """
    # Totales
    total_up = (await db.execute(
        select(func.count(MessageFeedback.id))
        .where(MessageFeedback.rating == "up")
    )).scalar() or 0

    total_down = (await db.execute(
        select(func.count(MessageFeedback.id))
        .where(MessageFeedback.rating == "down")
    )).scalar() or 0

    # Mensajes con más 👎 (peor calificados)
    worst_rows = (await db.execute(
        select(
            MessageFeedback.message_id,
            func.count(MessageFeedback.id).label("total_down"),
        )
        .where(MessageFeedback.rating == "down")
        .group_by(MessageFeedback.message_id)
        .order_by(func.count(MessageFeedback.id).desc())
        .limit(limit)
    )).all()

    # Satisfacción promedio
    avg_score = (await db.execute(
        select(func.avg(Conversation.satisfaction_score))
        .where(Conversation.satisfaction_score.isnot(None))
    )).scalar()

    total_surveys = (await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.satisfaction_score.isnot(None))
    )).scalar() or 0

    resolved_count = (await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.resolved_by_bot == True)  # noqa: E712
    )).scalar() or 0

    return {
        "feedback": {
            "total_up": total_up,
            "total_down": total_down,
            "approval_rate": round(total_up / max(total_up + total_down, 1) * 100, 1),
        },
        "satisfaction": {
            "total_surveys": total_surveys,
            "avg_score": round(float(avg_score), 2) if avg_score else None,
            "resolved_by_bot": resolved_count,
            "resolution_rate": round(resolved_count / max(total_surveys, 1) * 100, 1),
        },
        "worst_rated_messages": [
            {"message_id": str(r.message_id), "total_down": r.total_down}
            for r in worst_rows
        ],
    }