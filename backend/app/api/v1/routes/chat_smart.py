"""Fachada especializada del chat BOTIQ.

Intercepta dos flujos que deben resolverse de forma determinística y aislada:
1. Seguimiento de tickets Aranda, exclusivamente de lectura.
2. Consultas de salud e inventario de servidores mediante la KB independiente.

Todo lo demás se delega al endpoint original /chat/message, conservando sin
cambios FAQ, RAG de soporte, matriz, estado de aplicativos, diagnóstico,
búsqueda web, IA general y creación de ticket como última instancia.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_employee
from app.api.v1.routes.chat import send_message as legacy_send_message
from app.core.config import settings
from app.core.roles import UserRole
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.conversation import Conversation, Message, MessageRole, ModuleType
from app.models.user import User
from app.modules.servers_kb.service import servers_kb_service
from app.schemas.chat import ChatMessageResponse
from app.services.aranda_tracking_service import aranda_tracking_service
from app.services.audit_service import audit_service
from app.services.chat_guard_service import chat_guard_service

router = APIRouter()

_HISTORY_MAX_MESSAGES = 6
_HISTORY_MAX_CHARS = 600


async def _delegate_to_legacy(
    *,
    message: str,
    session_id: Optional[str],
    image: Optional[UploadFile],
    current_user: User,
    db: AsyncSession,
) -> ChatMessageResponse:
    return await legacy_send_message(
        message=message,
        session_id=session_id,
        image=image,
        current_user=current_user,
        db=db,
    )


async def _get_conversation(
    db: AsyncSession,
    current_user: User,
    session_id: str,
) -> Conversation:
    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == current_user.id,
                Conversation.session_id == session_id,
            )
        )
    ).scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Sesión no encontrada. Inicia una nueva conversación.",
        )
    return conversation


async def _load_history(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> List[Dict]:
    rows = (
        await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
            )
            .order_by(desc(Message.created_at))
            .limit(_HISTORY_MAX_MESSAGES)
        )
    ).scalars().all()

    history: List[Dict] = []
    for row in reversed(rows):
        content = (row.content or "")[:_HISTORY_MAX_CHARS]
        if not content:
            continue
        history.append(
            {
                "role": (
                    "model"
                    if row.role == MessageRole.ASSISTANT
                    else "user"
                ),
                "content": content,
            }
        )
    return history


def _close_on_question_limit(
    conversation: Conversation,
    response_text: str,
) -> str:
    if conversation.question_count < settings.MAX_QUESTIONS_PER_SESSION:
        return response_text

    response_text += (
        "\n\nHas alcanzado el límite de preguntas de esta sesión. "
        "La conversación será finalizada por control de consumo."
    )
    chat_guard_service.finish_conversation(
        conversation,
        "question_limit_reached",
        "ended",
    )
    return response_text


async def _handle_server_query(
    *,
    request: Request,
    message: str,
    session_id: str,
    conversation: Conversation,
    current_user: User,
    db: AsyncSession,
) -> ChatMessageResponse:
    """Responde con la KB de servidores sin pasar por web ni IA general."""
    history = await _load_history(db, conversation.id)

    conversation.module = ModuleType.SERVER_VALIDATION
    conversation.question_count = (conversation.question_count or 0) + 1

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
            metadata_={
                "server_kb_requested": True,
                "selected_profile": conversation.selected_profile,
                "question_number": conversation.question_count,
            },
        )
    )

    result = await servers_kb_service.generate_response(
        user_message=message,
        history=history,
    )
    response_text = _close_on_question_limit(
        conversation,
        result.get("text") or "No fue posible consultar el inventario.",
    )

    if not result.get("knowledge_gap"):
        chat_guard_service.mark_resolution_attempt(conversation)

    structured_data = dict(result.get("structured_data") or {})
    safe_status = {
        "source": "servers_kb",
        "mode": result.get("mode"),
        **structured_data,
    }

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            tokens_used=result.get("tokens_used") or 0,
            response_time_ms=result.get("response_time_ms") or 0,
            metadata_={
                "answer_source": "servers_rag",
                "servers_rag_used": True,
                "servers_kb_mode": result.get("mode"),
                "server_health": structured_data,
                "sources": result.get("sources") or [],
                "knowledge_gap": bool(result.get("knowledge_gap")),
                "module": ModuleType.SERVER_VALIDATION.value,
                "resolution_attempts": conversation.resolution_attempts,
            },
        )
    )

    await audit_service.log(
        db,
        "servers_kb_chat_query",
        current_user.id,
        ModuleType.SERVER_VALIDATION.value,
        {
            "session_id": session_id,
            "conversation_id": str(conversation.id),
            "mode": result.get("mode"),
            "knowledge_gap": bool(result.get("knowledge_gap")),
            "matched_servers": structured_data.get("matched_servers", []),
            "total_servers": structured_data.get("total_servers"),
            "tokens_used": result.get("tokens_used") or 0,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return ChatMessageResponse(
        response=response_text,
        session_id=session_id,
        module_used=ModuleType.SERVER_VALIDATION,
        conversation_id=conversation.id,
        tokens_used=result.get("tokens_used") or 0,
        has_image_analysis=False,
        escalated_to_aranda=bool(conversation.escalated_to_aranda),
        aranda_ticket_id=conversation.aranda_ticket_id,
        ticket_eligible=bool(conversation.ticket_eligible),
        sources=result.get("sources") or [],
        knowledge_gap=bool(result.get("knowledge_gap")),
        application_status=safe_status,
        session_status=conversation.session_status or "active",
        ended_reason=conversation.ended_reason,
        question_count=conversation.question_count or 0,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
        answer_source="servers_rag",
    )


async def _enforce_tracking_rate_limit(
    db: AsyncSession,
    current_user: User,
) -> None:
    configured_limit = str(
        getattr(settings, "ARANDA_TRACKING_RATE_LIMIT", "10/minute")
    )
    match = re.search(r"\d+", configured_limit)
    max_tracking_per_minute = max(
        1,
        int(match.group(0)) if match else 10,
    )
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


async def _handle_ticket_tracking(
    *,
    request: Request,
    message: str,
    session_id: str,
    conversation: Conversation,
    current_user: User,
    db: AsyncSession,
) -> ChatMessageResponse:
    await _enforce_tracking_rate_limit(db, current_user)

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
    response_text = _close_on_question_limit(
        conversation,
        result["message"],
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


@router.post("/message-smart", response_model=ChatMessageResponse)
async def send_smart_message(
    request: Request,
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """Intercepta Aranda y salud de servidores; delega lo demás."""
    tracking_request = aranda_tracking_service.is_tracking_request(message)
    server_request = (
        image is None
        and servers_kb_service.is_server_health_query(message)
    )

    if image is not None or (not tracking_request and not server_request):
        return await _delegate_to_legacy(
            message=message,
            session_id=session_id,
            image=image,
            current_user=current_user,
            db=db,
        )

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Debes iniciar la sesión antes de realizar la consulta.",
        )

    conversation = await _get_conversation(
        db,
        current_user,
        session_id,
    )

    guard = chat_guard_service.evaluate_message(conversation, message)
    if not guard.allowed:
        return await _delegate_to_legacy(
            message=message,
            session_id=session_id,
            image=None,
            current_user=current_user,
            db=db,
        )

    # El seguimiento de un número de ticket tiene prioridad sobre cualquier
    # coincidencia accidental con términos como servidor/estado.
    if tracking_request:
        return await _handle_ticket_tracking(
            request=request,
            message=message,
            session_id=session_id,
            conversation=conversation,
            current_user=current_user,
            db=db,
        )

    # El inventario de infraestructura es información restringida. Solo se
    # expone dentro de una sesión de soporte validada y para roles autorizados.
    authorized_for_servers = (
        conversation.selected_profile == "support_engineer"
        and bool(conversation.support_network_validated)
        and current_user.role in {
            UserRole.SUPPORT_ENGINEER,
            UserRole.ADMIN,
        }
    )
    if not authorized_for_servers:
        return await _delegate_to_legacy(
            message=message,
            session_id=session_id,
            image=None,
            current_user=current_user,
            db=db,
        )

    return await _handle_server_query(
        request=request,
        message=message,
        session_id=session_id,
        conversation=conversation,
        current_user=current_user,
        db=db,
    )
