"""Fachada del chat que intercepta seguimiento de tickets sin alterar el flujo actual."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_employee
from app.api.v1.routes.chat import send_message as legacy_send_message
from app.core.config import settings
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation, Message, MessageRole
from app.models.user import User
from app.schemas.chat import ChatMessageResponse
from app.services.aranda_tracking_service import aranda_tracking_service
from app.services.audit_service import audit_service
from app.services.chat_guard_service import chat_guard_service

router = APIRouter()


@router.post("/message-smart", response_model=ChatMessageResponse)
async def send_smart_message(
    request: Request,
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """Mantiene el chat existente y agrega seguimiento Aranda de solo lectura.

    Las consultas normales se delegan al endpoint original. Solo se intercepta
    cuando el mensaje expresa seguimiento/estado de ticket. Así no se modifica
    la cadena actual FAQ → RAG → estado → diagnóstico → creación última instancia.
    """
    if image is not None or not aranda_tracking_service.is_tracking_request(message):
        return await legacy_send_message(
            message=message,
            session_id=session_id,
            image=image,
            current_user=current_user,
            db=db,
        )

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Debes iniciar la sesión antes de consultar un ticket.",
        )

    # Rate limit distribuido usando la auditoría en PostgreSQL. A diferencia de
    # un contador en memoria, funciona con varios workers/instancias y solo se
    # aplica al seguimiento, no a las preguntas normales del chat.
    configured_limit = str(getattr(settings, "ARANDA_TRACKING_RATE_LIMIT", "10/minute"))
    match = re.search(r"\d+", configured_limit)
    max_tracking_per_minute = max(1, int(match.group(0)) if match else 10)
    tracking_actions = [
        "aranda_tracking_requested",
        "aranda_tracking_success",
        "aranda_tracking_denied",
        "aranda_tracking_not_found",
        "aranda_tracking_error",
    ]
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent_tracking = (
        await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == current_user.id,
                AuditLog.action.in_(tracking_actions),
                AuditLog.created_at >= cutoff,
            )
        )
    ).scalar() or 0
    if recent_tracking >= max_tracking_per_minute:
        raise HTTPException(
            status_code=429,
            detail=(
                "Has realizado demasiadas consultas de seguimiento. "
                "Espera un minuto antes de intentarlo nuevamente."
            ),
        )

    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == current_user.id,
                Conversation.session_id == session_id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Sesión no encontrada. Inicia una nueva conversación.")

    # Conserva los controles del chat actual (sesión finalizada, longitud,
    # alcance empresarial, etc.). Si el guard bloquea, delegamos al endpoint
    # original para no duplicar su lógica ni sus mensajes.
    guard = chat_guard_service.evaluate_message(conversation, message)
    if not guard.allowed:
        return await legacy_send_message(
            message=message,
            session_id=session_id,
            image=None,
            current_user=current_user,
            db=db,
        )

    conversation.question_count = (conversation.question_count or 0) + 1
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
            metadata_={"ticket_tracking_requested": True},
        )
    )

    result = await aranda_tracking_service.track_message(
        message=message,
        conversation=conversation,
        current_user=current_user,
    )
    response_text = result["message"]

    if conversation.question_count >= settings.MAX_QUESTIONS_PER_SESSION:
        response_text += (
            "\n\nHas alcanzado el límite de preguntas de esta sesión. "
            "La conversación será finalizada por control de consumo."
        )
        chat_guard_service.finish_conversation(
            conversation,
            "question_limit_reached",
            "ended",
        )

    safe_metadata = dict(result.get("safe_metadata") or {})
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            tokens_used=0,
            metadata_={
                "answer_source": "aranda_tracking",
                "ticket_tracking": safe_metadata,
                "read_only": True,
            },
        )
    )

    await audit_service.log(
        db,
        result.get("audit_action") or "aranda_tracking_requested",
        current_user.id,
        "chat",
        {
            "session_id": session_id,
            "conversation_id": str(conversation.id),
            # safe_metadata fue diseñado para no incluir sessionId de Aranda,
            # tokens, URLs de adjuntos ni notas privadas.
            **safe_metadata,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return ChatMessageResponse(
        response=response_text,
        session_id=session_id,
        module_used=conversation.module,
        conversation_id=conversation.id,
        tokens_used=0,
        has_image_analysis=False,
        escalated_to_aranda=bool(conversation.escalated_to_aranda),
        aranda_ticket_id=conversation.aranda_ticket_id,
        ticket_eligible=bool(conversation.ticket_eligible),
        sources=["Aranda Service Desk"],
        knowledge_gap=False,
        application_status=None,
        session_status=conversation.session_status or "active",
        ended_reason=conversation.ended_reason,
        question_count=conversation.question_count or 0,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
        answer_source="aranda_tracking",
        ticket_tracking=result.get("ticket_tracking"),
    )
