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



def _build_employee_server_response(result: Dict) -> Dict:
    """Construye una respuesta sanitizada para el perfil Empleado.

    Nunca expone porcentajes de CPU/RAM/disco, sistema operativo, capacidad,
    reinicios, notas técnicas, conteos globales ni listado de servidores. Solo
    informa una categoría general de salud y registra si requiere revisión.
    """
    structured = dict(result.get("structured_data") or {})
    mode = str(result.get("mode") or structured.get("mode") or "unknown")
    freshness = dict(structured.get("freshness") or {})
    stale = bool(freshness.get("stale"))
    knowledge_gap = bool(result.get("knowledge_gap"))

    server_summaries = [
        item
        for item in (structured.get("servers") or [])
        if isinstance(item, dict)
    ]
    matched_servers = [
        str(value).strip()
        for value in (structured.get("matched_servers") or [])
        if str(value).strip()
    ]
    names = [
        str(item.get("hostname") or "").strip()
        for item in server_summaries
        if str(item.get("hostname") or "").strip()
    ] or matched_servers
    server_label = ", ".join(names[:3]) if names else "el servidor consultado"

    status_keys = {
        str(item.get("status_key") or "unknown").strip().lower()
        for item in server_summaries
    }

    health = "unknown"
    requires_support = False

    if mode == "empty_index":
        text = (
            "En este momento no pude consultar el estado de la infraestructura. "
            "La solicitud quedó registrada para revisión del equipo de soporte."
        )
        requires_support = True
    elif mode == "hostname_not_found":
        candidate = str(structured.get("candidate") or "").strip()
        target = f" **{candidate}**" if candidate else ""
        text = (
            f"No pude confirmar el servidor{target} en el inventario disponible. "
            "Verifica el nombre y, si el inconveniente continúa, comunícate con "
            "el equipo de soporte."
        )
    elif mode == "exact_hostname":
        if "critical" in status_keys:
            health = "critical"
            requires_support = True
            text = (
                f"{server_label} presenta una condición crítica y requiere "
                "validación técnica. La consulta quedó registrada para revisión "
                "del equipo de soporte."
            )
        elif "unreachable" in status_keys:
            health = "unreachable"
            requires_support = True
            text = (
                f"No fue posible confirmar la disponibilidad de {server_label} "
                "porque aparece inalcanzable. La consulta quedó registrada para "
                "revisión del equipo de soporte."
            )
        elif "warning" in status_keys:
            health = "warning"
            requires_support = True
            text = (
                f"{server_label} presenta una condición de advertencia. "
                "La consulta quedó registrada para que el equipo de soporte "
                "realice las validaciones correspondientes."
            )
        elif "healthy" in status_keys:
            health = "healthy"
            text = (
                f"{server_label} se encuentra operativo y no presenta alertas "
                "generales en el último reporte disponible."
            )
        else:
            text = (
                f"No pude confirmar con suficiente precisión el estado de "
                f"{server_label}. La consulta quedó registrada para revisión "
                "del equipo de soporte."
            )
            requires_support = True
    elif mode in {
        "global_summary",
        "critical",
        "unreachable",
        "warning",
        "healthy",
        "cpu_threshold",
        "ram_threshold",
        "disk_threshold",
    }:
        counts = dict(structured.get("counts") or {})
        alerts = dict(structured.get("alerts") or {})
        has_critical = int(counts.get("critical") or 0) > 0
        has_unreachable = int(counts.get("unreachable") or 0) > 0
        has_warning = int(counts.get("warning") or 0) > 0
        has_metric_alerts = any(int(value or 0) > 0 for value in alerts.values())
        has_matches = bool(matched_servers)

        if has_critical or has_unreachable or has_metric_alerts or has_matches:
            health = "attention_required"
            requires_support = True
            text = (
                "El estado general de la infraestructura presenta alertas que "
                "requieren validación técnica. La consulta quedó registrada para "
                "revisión del equipo de soporte."
            )
        elif has_warning:
            health = "warning"
            requires_support = True
            text = (
                "La infraestructura presenta condiciones de advertencia. "
                "La consulta quedó registrada para que el equipo de soporte "
                "realice las validaciones correspondientes."
            )
        else:
            health = "healthy"
            text = (
                "La infraestructura reportada se encuentra estable y no presenta "
                "alertas generales en la última actualización disponible."
            )
    elif knowledge_gap:
        text = (
            "No pude confirmar el estado solicitado con la información disponible. "
            "La consulta quedó registrada para revisión del equipo de soporte."
        )
        requires_support = True
    else:
        text = (
            "La consulta corresponde a información técnica restringida. "
            "El equipo de soporte puede realizar una validación más detallada."
        )
        requires_support = True

    if stale:
        text += (
            "\n\nLa información disponible puede no reflejar el estado más reciente."
        )

    return {
        "text": text,
        "health": health,
        "requires_support": requires_support,
        "stale": stale,
        "mode": mode,
        "server_names": names[:3],
    }


async def _handle_server_query(
    *,
    request: Request,
    message: str,
    session_id: str,
    conversation: Conversation,
    current_user: User,
    db: AsyncSession,
    detail_level: str = "full",
) -> ChatMessageResponse:
    """Responde con la KB de servidores sin pasar por web ni IA general.

    detail_level="basic" se usa para el perfil Empleado y nunca expone
    métricas internas. detail_level="full" queda reservado para soporte.
    """
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
    structured_data = dict(result.get("structured_data") or {})
    is_basic = detail_level == "basic"

    if is_basic:
        employee_view = _build_employee_server_response(result)
        raw_response_text = employee_view["text"]
        response_sources: List[str] = []
        safe_status = {
            "source": "servers_kb",
            "mode": employee_view["mode"],
            "summary_level": "basic",
            "health": employee_view["health"],
            "requires_support": employee_view["requires_support"],
            "stale": employee_view["stale"],
        }
        if employee_view["server_names"]:
            safe_status["server"] = employee_view["server_names"][0]
    else:
        employee_view = None
        raw_response_text = (
            result.get("text") or "No fue posible consultar el inventario."
        )
        response_sources = result.get("sources") or []
        safe_status = {
            "source": "servers_kb",
            "mode": result.get("mode"),
            "summary_level": "full",
            **structured_data,
        }

    response_text = _close_on_question_limit(
        conversation,
        raw_response_text,
    )

    if not result.get("knowledge_gap"):
        chat_guard_service.mark_resolution_attempt(conversation)

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
                "server_health": safe_status if is_basic else structured_data,
                "employee_summary": bool(is_basic),
                "attention_required": bool(
                    employee_view and employee_view["requires_support"]
                ),
                "sources": response_sources,
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
            "detail_level": detail_level,
            "knowledge_gap": bool(result.get("knowledge_gap")),
            "attention_required": bool(
                employee_view and employee_view["requires_support"]
            ),
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
        sources=response_sources,
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

    # El perfil Empleado puede consultar únicamente una conclusión básica.
    # Nunca recibe CPU, RAM, disco, sistema operativo, reinicios, notas,
    # conteos globales ni listados de infraestructura.
    if conversation.selected_profile == "employee":
        return await _handle_server_query(
            request=request,
            message=message,
            session_id=session_id,
            conversation=conversation,
            current_user=current_user,
            db=db,
            detail_level="basic",
        )

    # El detalle completo continúa restringido a una sesión de soporte
    # validada y a roles autorizados.
    authorized_for_full_detail = (
        conversation.selected_profile == "support_engineer"
        and bool(conversation.support_network_validated)
        and current_user.role in {
            UserRole.SUPPORT_ENGINEER,
            UserRole.ADMIN,
        }
    )
    if not authorized_for_full_detail:
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
        detail_level="full",
    )
