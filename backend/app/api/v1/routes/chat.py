from datetime import datetime, timedelta, timezone
from typing import List, Optional
import base64
import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_admin, require_employee
from app.core.config import settings
from app.core.roles import UserRole, can_access_module
from app.db.session import get_db
from app.models.conversation import Conversation, Message, MessageRole, ModuleType
from app.models.user import User
from app.modules.employee_bot.service import employee_bot_service
from app.modules.intent_classifier.service import intent_classifier_service
from app.modules.server_monitor.service import server_monitor_service
from app.modules.support_rag.service import support_rag_service
from app.schemas.chat import (
    AdminConversationLogItem,
    ChatMessageResponse,
    ChatSessionStartRequest,
    ChatSessionStartResponse,
    ConversationItem,
    MessageItem,
)
from app.services.application_status_service import application_status_service
from app.services.aranda_service import aranda_service
from app.services.audit_service import audit_service
from app.services.chat_guard_service import chat_guard_service
from app.services.gcs_service import gcs_service
from app.services.vertex.gemini_vision_service import gemini_vision_service

router = APIRouter()

MODULE_PERM = {
    ModuleType.EMPLOYEE: "employee_chat",
    ModuleType.SUPPORT_RAG: "support_rag",
    ModuleType.SERVER_VALIDATION: "server_validation",
}


def _welcome_message(profile: str, support_validated: bool = False) -> str:
    if profile == "support_engineer":
        return (
            "Perfil configurado como Ingeniero de Soporte."
            + (" Usuario de red validado." if support_validated else "")
            + "\n\nPuedes consultarme sobre documentación técnica, procedimientos, base de conocimiento, servidores, URLs, aplicativos e incidentes corporativos."
        )

    return (
        "Perfil configurado como Empleado.\n\n"
        "Puedo ayudarte con accesos, errores de aplicaciones, correo, VPN, portales, URLs, disponibilidad de servicios y soporte técnico básico."
    )


def _module_from_profile_and_message(conversation: Conversation, current_user: User, message: str) -> ModuleType:
    if conversation.selected_profile == "employee":
        return ModuleType.EMPLOYEE
    return conversation.module or ModuleType.SUPPORT_RAG


async def _classify_support_module(message: str) -> ModuleType:
    intent = await intent_classifier_service.classify(message)
    return intent.module


def _compose_app_status_message(status: dict) -> str:
    if not status:
        return ""

    state = str(status.get("status") or "unknown").lower()
    service = status.get("service_name") or status.get("name") or "el servicio consultado"
    msg = status.get("message") or ""

    if state in {"down", "failed", "error", "critical", "offline"}:
        return (
            f"Validé el estado de {service} y en este momento aparece con estado **{state}**. "
            f"{msg}\n\nRecomendación: espera unos minutos y vuelve a intentar. Si el problema continúa, puedo ayudarte a validar los pasos previos antes de escalar a Aranda."
        )

    if state in {"degraded", "warning", "slow"}:
        return (
            f"Validé el estado de {service} y aparece con degradación o advertencia (**{state}**). "
            f"{msg}\n\nPuede que el acceso esté intermitente. Te recomiendo intentar nuevamente y confirmar si el error persiste."
        )

    if state in {"up", "ok", "healthy", "online"}:
        return (
            f"Validé el estado de {service} y aparece operativo (**{state}**). "
            f"{msg}\n\nSi sigues sin poder ingresar, revisemos credenciales, VPN, caché del navegador, permisos o el mensaje de error exacto."
        )

    return f"Consulté el estado de {service}, pero la respuesta fue indeterminada: {status}"


@router.post("/session/start", response_model=ChatSessionStartResponse)
async def start_session(
    data: ChatSessionStartRequest,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    session_id = str(uuid.uuid4())
    selected_profile = data.selected_profile
    support_validated = False
    module = ModuleType.EMPLOYEE

    if selected_profile == "support_engineer":
        ok, reason = await chat_guard_service.validate_support_network_user(db, current_user, data.network_username)
        if not ok:
            await audit_service.log(
                db,
                "support_network_validation_failed",
                current_user.id,
                "chat",
                {"network_username": data.network_username, "reason": reason},
            )
            await db.commit()
            raise HTTPException(status_code=403, detail=reason)
        support_validated = True
        module = ModuleType.SUPPORT_RAG

    conversation = Conversation(
        user_id=current_user.id,
        session_id=session_id,
        selected_profile=selected_profile,
        module=module,
        session_status="active",
        support_network_username=(data.network_username or "").strip().lower() if data.network_username else None,
        support_network_validated=support_validated,
        metadata_={
            "started_by_user_role": current_user.role.value,
            "max_questions": settings.MAX_QUESTIONS_PER_SESSION,
            "flow": "employee_faq_or_support_rag",
        },
    )
    db.add(conversation)
    await db.flush()

    welcome = _welcome_message(selected_profile, support_validated)
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.SYSTEM,
            content=welcome,
            metadata_={"event": "session_started", "selected_profile": selected_profile},
        )
    )
    await audit_service.log(
        db,
        "chat_session_started",
        current_user.id,
        "chat",
        {"session_id": session_id, "conversation_id": str(conversation.id), "selected_profile": selected_profile},
    )
    await db.commit()
    await db.refresh(conversation)

    return ChatSessionStartResponse(
        session_id=session_id,
        conversation_id=conversation.id,
        selected_profile=selected_profile,
        module_used=module,
        support_network_validated=support_validated,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
        welcome_message=welcome,
    )


@router.get("/conversations", response_model=List[ConversationItem])
async def list_conversations(
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageItem])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    messages = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return messages.scalars().all()


def _normalize_date_range(date_from: Optional[datetime], date_to: Optional[datetime]):
    """Normaliza fechas de filtros: asegura tz UTC y hace date_to inclusivo (fin de día)."""
    if date_from and date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=timezone.utc)
    if date_to:
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)
        # Si viene solo la fecha (00:00), incluir todo el día.
        if date_to.hour == 0 and date_to.minute == 0 and date_to.second == 0:
            date_to = date_to + timedelta(days=1)
    return date_from, date_to


async def _fetch_admin_logs(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    selected_profile: Optional[str],
    session_status: Optional[str],
    q: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    limit: int,
) -> List[AdminConversationLogItem]:
    """Lógica compartida entre el listado de logs y la exportación CSV."""
    date_from, date_to = _normalize_date_range(date_from, date_to)

    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.user), selectinload(Conversation.messages))
        .order_by(desc(Conversation.created_at))
        .limit(limit)
    )

    if user_id:
        stmt = stmt.where(Conversation.user_id == user_id)
    if selected_profile:
        stmt = stmt.where(Conversation.selected_profile == selected_profile)
    if session_status:
        stmt = stmt.where(Conversation.session_status == session_status)
    if date_from:
        stmt = stmt.where(Conversation.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Conversation.created_at < date_to)

    result = await db.execute(stmt)
    conversations = result.scalars().unique().all()

    rows: List[AdminConversationLogItem] = []
    q_norm = (q or "").lower().strip()

    for conv in conversations:
        user_messages = [
            msg.content for msg in sorted(conv.messages, key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))
            if msg.role == MessageRole.USER
        ]
        all_text = " ".join(user_messages).lower()

        haystack = " ".join(
            filter(
                None,
                [
                    all_text,
                    (conv.user.email if conv.user else "").lower(),
                    (conv.user.full_name if conv.user else "").lower(),
                    (conv.detected_url or "").lower(),
                    (conv.detected_ip or "").lower(),
                    (conv.aranda_ticket_id or "").lower(),
                ],
            )
        )
        if q_norm and q_norm not in haystack:
            continue

        last_msg = user_messages[-1][:255] if user_messages else None

        rows.append(
            AdminConversationLogItem(
                id=conv.id,
                user_id=conv.user_id,
                user_email=conv.user.email if conv.user else "",
                user_full_name=conv.user.full_name if conv.user else "",
                session_id=conv.session_id,
                selected_profile=conv.selected_profile,
                module=conv.module,
                session_status=conv.session_status or "active",
                ended_reason=conv.ended_reason,
                question_count=conv.question_count or 0,
                out_of_scope_count=conv.out_of_scope_count or 0,
                resolution_attempts=conv.resolution_attempts or 0,
                ticket_eligible=bool(conv.ticket_eligible),
                support_network_username=conv.support_network_username,
                support_network_validated=bool(conv.support_network_validated),
                detected_url=conv.detected_url,
                detected_ip=conv.detected_ip,
                escalated_to_aranda=bool(conv.escalated_to_aranda),
                aranda_ticket_id=conv.aranda_ticket_id,
                aranda_ticket_status=conv.aranda_ticket_status,
                created_at=conv.created_at,
                ended_at=conv.ended_at,
                last_message=last_msg,
            )
        )

    return rows


@router.get("/admin/conversation-logs", response_model=List[AdminConversationLogItem])
async def admin_conversation_logs(
    user_id: Optional[uuid.UUID] = Query(None),
    selected_profile: Optional[str] = Query(None),
    session_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await _fetch_admin_logs(db, user_id, selected_profile, session_status, q, date_from, date_to, limit)


@router.get("/admin/conversation-logs/export")
async def admin_conversation_logs_export(
    user_id: Optional[uuid.UUID] = Query(None),
    selected_profile: Optional[str] = Query(None),
    session_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(500, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Reportería: exporta los logs de conversaciones filtrados como CSV (compatible con Excel)."""
    rows = await _fetch_admin_logs(db, user_id, selected_profile, session_status, q, date_from, date_to, limit)

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "conversation_id",
            "fecha_inicio",
            "fecha_fin",
            "usuario",
            "correo",
            "perfil",
            "modulo",
            "estado_sesion",
            "motivo_fin",
            "preguntas",
            "fuera_de_alcance",
            "intentos_solucion",
            "usuario_red",
            "red_validado",
            "url_detectada",
            "ip_detectada",
            "ticket_elegible",
            "escalado_aranda",
            "ticket_aranda_id",
            "ticket_aranda_estado",
            "ultima_consulta",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                str(r.id),
                r.created_at.isoformat() if r.created_at else "",
                r.ended_at.isoformat() if r.ended_at else "",
                r.user_full_name,
                r.user_email,
                r.selected_profile or "",
                r.module.value if r.module else "",
                r.session_status,
                r.ended_reason or "",
                r.question_count,
                r.out_of_scope_count,
                r.resolution_attempts,
                r.support_network_username or "",
                "si" if r.support_network_validated else "no",
                r.detected_url or "",
                r.detected_ip or "",
                "si" if r.ticket_eligible else "no",
                "si" if r.escalated_to_aranda else "no",
                r.aranda_ticket_id or "",
                r.aranda_ticket_status or "",
                (r.last_message or "").replace("\n", " ").replace("\r", " "),
            ]
        )

    await audit_service.log(
        db,
        "conversation_logs_exported",
        current_user.id,
        "reports",
        {"rows": len(rows), "filters": {"selected_profile": selected_profile, "session_status": session_status, "q": q}},
    )
    await db.commit()

    filename = f"botiq_conversation_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    # BOM utf-8-sig para que Excel detecte la codificación correctamente.
    csv_bytes = ("\ufeff" + buffer.getvalue()).encode("utf-8")

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/conversation-logs/{conversation_id}/messages", response_model=List[MessageItem])
async def admin_conversation_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Permite al administrador ver la conversación completa de cualquier usuario (auditoría)."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    messages = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )

    await audit_service.log(
        db,
        "admin_conversation_viewed",
        current_user.id,
        "reports",
        {"conversation_id": str(conversation_id)},
    )
    await db.commit()

    return messages.scalars().all()


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    if not session_id:
        raise HTTPException(status_code=400, detail="Debes iniciar la sesión seleccionando si eres Empleado o Ingeniero de Soporte.")

    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Sesión no encontrada. Inicia una nueva conversación.")

    guard = chat_guard_service.evaluate_message(conversation, message)
    if not guard.allowed:
        if guard.reason == "out_of_scope_warning":
            conversation.out_of_scope_count = (conversation.out_of_scope_count or 0) + 1
        if guard.end_session:
            chat_guard_service.finish_conversation(conversation, guard.reason or "session_ended", guard.status)

        db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message, metadata_={"blocked_by_guard": True, "reason": guard.reason}))
        db.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=guard.final_message or "Consulta no permitida.", metadata_={"guard_response": True, "reason": guard.reason}))
        await audit_service.log(db, "chat_message_blocked", current_user.id, "chat", {"session_id": session_id, "reason": guard.reason})
        await db.commit()

        return ChatMessageResponse(
            response=guard.final_message or "Consulta no permitida.",
            session_id=session_id,
            module_used=conversation.module,
            conversation_id=conversation.id,
            tokens_used=0,
            session_status=conversation.session_status,
            ended_reason=conversation.ended_reason,
            question_count=conversation.question_count or 0,
            max_questions=settings.MAX_QUESTIONS_PER_SESSION,
            ticket_eligible=bool(conversation.ticket_eligible),
            aranda_ticket_id=conversation.aranda_ticket_id,
        )

    image_analysis = None
    image_gcs_url = None

    if image and image.filename:
        img_bytes = await image.read()
        if len(img_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")
        if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail=f"Tipo no soportado: {image.content_type}")

        b64 = base64.b64encode(img_bytes).decode()
        image_gcs_url = await gcs_service.upload_image(b64, image.content_type)
        vision_result = await gemini_vision_service.analyze_error_screenshot(b64, image.content_type)
        image_analysis = vision_result.get("description")

    # Si el usuario pide ticket, primero valida elegibilidad.
    if chat_guard_service.asks_for_ticket(message):
        can_ticket, reason = chat_guard_service.can_create_ticket(conversation)
        if not can_ticket:
            db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message, metadata_={"ticket_requested": True}))
            db.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=reason, metadata_={"ticket_denied": True}))
            await audit_service.log(db, "aranda_ticket_denied", current_user.id, "chat", {"session_id": session_id, "reason": reason})
            await db.commit()

            return ChatMessageResponse(
                response=reason,
                session_id=session_id,
                module_used=conversation.module,
                conversation_id=conversation.id,
                tokens_used=0,
                session_status=conversation.session_status,
                ended_reason=conversation.ended_reason,
                question_count=conversation.question_count or 0,
                max_questions=settings.MAX_QUESTIONS_PER_SESSION,
                ticket_eligible=bool(conversation.ticket_eligible),
                aranda_ticket_id=conversation.aranda_ticket_id,
            )

        description = aranda_service.build_ticket_description(conversation, message)
        ticket_result = await aranda_service.create_ticket(
            conversation=conversation,
            current_user=current_user,
            subject=f"BOTIQ - Caso de soporte {conversation.detected_url or conversation.detected_ip or ''}".strip(),
            description=description,
            application_status=conversation.application_status_snapshot,
        )
        aranda_service.mark_ticket_result(conversation, ticket_result)

        db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message, metadata_={"ticket_requested": True}))
        db.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=ticket_result["message"], metadata_={"ticket_result": ticket_result}))
        await audit_service.log(db, "aranda_ticket_requested", current_user.id, "chat", {"session_id": session_id, "result": ticket_result})
        await db.commit()

        return ChatMessageResponse(
            response=ticket_result["message"],
            session_id=session_id,
            module_used=conversation.module,
            conversation_id=conversation.id,
            tokens_used=0,
            escalated_to_aranda=bool(ticket_result.get("created")),
            aranda_ticket_id=conversation.aranda_ticket_id,
            ticket_eligible=bool(conversation.ticket_eligible),
            session_status=conversation.session_status,
            ended_reason=conversation.ended_reason,
            question_count=conversation.question_count or 0,
            max_questions=settings.MAX_QUESTIONS_PER_SESSION,
        )

    if conversation.selected_profile == "support_engineer":
        if current_user.role not in {UserRole.SUPPORT_ENGINEER, UserRole.ADMIN}:
            raise HTTPException(status_code=403, detail="No tienes permiso para operar como Ingeniero de Soporte.")
        module = await _classify_support_module(message)
    else:
        module = ModuleType.EMPLOYEE

    if not can_access_module(current_user.role, MODULE_PERM.get(module, "employee_chat")):
        raise HTTPException(status_code=403, detail=f"Sin permiso para módulo: {module.value}")

    conversation.module = module
    conversation.question_count = (conversation.question_count or 0) + 1

    detected_url = chat_guard_service.extract_url(message)
    detected_ip = chat_guard_service.extract_ip(message)

    if detected_url:
        conversation.detected_url = detected_url
    if detected_ip:
        conversation.detected_ip = detected_ip

    app_status = None
    app_status_text = ""

    if detected_url or detected_ip or chat_guard_service.asks_about_url_or_service(message):
        app_status = await application_status_service.lookup(url=detected_url, ip=detected_ip, query=message)
        conversation.application_status_snapshot = app_status
        app_status_text = application_status_service.format_for_prompt(app_status)

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
            has_image=bool(image_analysis),
            image_gcs_url=image_gcs_url,
            metadata_={
                "selected_profile": conversation.selected_profile,
                "question_number": conversation.question_count,
                "detected_url": detected_url,
                "detected_ip": detected_ip,
                "application_status": app_status,
            },
        )
    )

    bot_result = None

    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)
        enriched_message = message
        if app_status_text:
            enriched_message = f"{message}\n\nInformación interna consultada por BOTIQ:\n{app_status_text}"
        bot_result = await employee_bot_service.generate_response(
            enriched_message,
            image_analysis=image_analysis,
            faq_context=faq,
            db=db,
        )
    elif module == ModuleType.SUPPORT_RAG:
        enriched_message = message
        if app_status_text:
            enriched_message = f"{message}\n\nInformación operativa interna:\n{app_status_text}"
        bot_result = await support_rag_service.generate_response(enriched_message, image_analysis=image_analysis)
    else:
        bot_result = await server_monitor_service.analyze_and_respond(message, image_analysis=image_analysis)

    if app_status:
        bot_result["application_status"] = app_status
        if app_status.get("found"):
            status_reply = _compose_app_status_message(app_status)
            if status_reply and module == ModuleType.EMPLOYEE:
                bot_result["text"] = f"{status_reply}\n\n{bot_result['text']}"

    # Cuenta como intento de solución si se usó FAQ, RAG, estado aplicativo o se detectó brecha.
    if app_status or bot_result.get("faq_used") or bot_result.get("sources") or bot_result.get("knowledge_gap"):
        chat_guard_service.mark_resolution_attempt(conversation)

    if bot_result.get("knowledge_gap"):
        conversation.ticket_eligible = conversation.ticket_eligible or conversation.resolution_attempts >= settings.MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET

    if conversation.question_count >= settings.MAX_QUESTIONS_PER_SESSION:
        bot_result["text"] = (
            f"{bot_result['text']}\n\n"
            f"Has alcanzado el límite de {settings.MAX_QUESTIONS_PER_SESSION} preguntas para esta sesión. "
            "Por control de consumo de IA, esta conversación será finalizada."
        )
        chat_guard_service.finish_conversation(conversation, "question_limit_reached", "ended")

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=bot_result["text"],
            tokens_used=bot_result.get("tokens_used"),
            response_time_ms=bot_result.get("response_time_ms"),
            metadata_={
                "sources": bot_result.get("sources"),
                "knowledge_gap": bot_result.get("knowledge_gap"),
                "module": module.value,
                "application_status": app_status,
                "resolution_attempts": conversation.resolution_attempts,
                "ticket_eligible": conversation.ticket_eligible,
            },
        )
    )

    if bot_result.get("escalated_to_aranda"):
        conversation.ticket_eligible = True

    if bot_result.get("knowledge_gap"):
        from app.models.knowledge_gap import KnowledgeGap

        existing = (
            await db.execute(select(KnowledgeGap).where(KnowledgeGap.query == message[:255]))
        ).scalar_one_or_none()

        if existing:
            existing.frequency += 1
            existing.last_seen = datetime.now(timezone.utc)
        else:
            db.add(
                KnowledgeGap(
                    query=message[:255],
                    module=module.value,
                    user_role=current_user.role.value,
                    avg_confidence=bot_result.get("avg_confidence", 0),
                    last_seen=datetime.now(timezone.utc),
                )
            )

    await audit_service.log(
        db,
        "chat_message_sent",
        current_user.id,
        module.value,
        {
            "session_id": session_id,
            "question_count": conversation.question_count,
            "tokens_used": bot_result.get("tokens_used"),
            "selected_profile": conversation.selected_profile,
            "detected_url": detected_url,
            "detected_ip": detected_ip,
            "ticket_eligible": conversation.ticket_eligible,
        },
    )
    await db.commit()

    return ChatMessageResponse(
        response=bot_result["text"],
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=bot_result.get("tokens_used"),
        has_image_analysis=bool(image_analysis),
        escalated_to_aranda=bool(conversation.escalated_to_aranda),
        aranda_ticket_id=conversation.aranda_ticket_id,
        ticket_eligible=bool(conversation.ticket_eligible),
        sources=bot_result.get("sources"),
        knowledge_gap=bot_result.get("knowledge_gap", False),
        application_status=app_status,
        session_status=conversation.session_status,
        ended_reason=conversation.ended_reason,
        question_count=conversation.question_count or 0,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
    )


@router.post("/session/{session_id}/end")
async def end_session(
    session_id: str,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
            Conversation.ended_at.is_(None),
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        chat_guard_service.finish_conversation(conversation, "user_closed_session", "ended")
        await audit_service.log(db, "chat_session_ended", current_user.id, "chat", {"session_id": session_id, "conversation_id": str(conversation.id)})
        await db.commit()

    return {"message": "Sesión cerrada", "session_id": session_id}
