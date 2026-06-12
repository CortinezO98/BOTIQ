from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import base64

from app.db.session import get_db
from app.api.deps import require_employee, require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType, MessageRole
from app.schemas.chat import ChatMessageResponse, ConversationItem, MessageItem, ChatSessionStartRequest, ChatSessionStartResponse, AdminConversationLogItem
from app.core.config import settings
from app.core.roles import UserRole, can_access_module
from app.modules.employee_bot.service import employee_bot_service
from app.modules.support_rag.service import support_rag_service
from app.modules.server_monitor.service import server_monitor_service
from app.modules.intent_classifier.service import intent_classifier_service
from app.services.vertex.gemini_vision_service import gemini_vision_service
from app.services.gcs_service import gcs_service
from app.services.audit_service import audit_service
from app.services.chat_guard_service import chat_guard_service

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
            + "\n\nPuedes consultarme sobre documentación técnica, procedimientos, base de conocimiento, servidores e incidentes corporativos."
        )
    return "Perfil configurado como Empleado.\n\nPuedo ayudarte con accesos, errores en aplicaciones, correo, VPN, portal y soporte técnico básico."


@router.post("/session/start", response_model=ChatSessionStartResponse)
async def start_session(data: ChatSessionStartRequest, current_user: User = Depends(require_employee), db: AsyncSession = Depends(get_db)):
    session_id = str(uuid.uuid4())
    selected_profile = data.selected_profile
    support_validated = False
    module = ModuleType.EMPLOYEE

    if selected_profile == "support_engineer":
        ok, reason = await chat_guard_service.validate_support_network_user(db, current_user, data.network_username)
        if not ok:
            await audit_service.log(db, "support_network_validation_failed", current_user.id, "chat", {"network_username": data.network_username, "reason": reason})
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
        metadata_={"started_by_user_role": current_user.role.value, "max_questions": settings.MAX_QUESTIONS_PER_SESSION},
    )
    db.add(conversation)
    await db.flush()

    welcome = _welcome_message(selected_profile, support_validated)
    db.add(Message(conversation_id=conversation.id, role=MessageRole.SYSTEM, content=welcome, metadata_={"event": "session_started", "selected_profile": selected_profile}))
    await audit_service.log(db, "chat_session_started", current_user.id, "chat", {"session_id": session_id, "conversation_id": str(conversation.id), "selected_profile": selected_profile})
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
async def list_conversations(current_user: User = Depends(require_employee), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id).order_by(Conversation.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageItem])
async def get_conversation_messages(conversation_id: uuid.UUID, current_user: User = Depends(require_employee), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    messages = await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()))
    return messages.scalars().all()


@router.get("/admin/conversation-logs", response_model=List[AdminConversationLogItem])
async def admin_conversation_logs(
    user_id: Optional[uuid.UUID] = Query(None),
    selected_profile: Optional[str] = Query(None),
    session_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(Conversation).options(selectinload(Conversation.user), selectinload(Conversation.messages)).order_by(desc(Conversation.created_at)).limit(limit)
    if user_id:
        stmt = stmt.where(Conversation.user_id == user_id)
    if selected_profile:
        stmt = stmt.where(Conversation.selected_profile == selected_profile)
    if session_status:
        stmt = stmt.where(Conversation.session_status == session_status)

    result = await db.execute(stmt)
    conversations = result.scalars().unique().all()
    rows = []
    for conv in conversations:
        last_msg = None
        for msg in sorted(conv.messages, key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            if msg.role == MessageRole.USER:
                last_msg = msg.content[:255]
                break
        rows.append(AdminConversationLogItem(
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
            support_network_username=conv.support_network_username,
            support_network_validated=bool(conv.support_network_validated),
            escalated_to_aranda=bool(conv.escalated_to_aranda),
            created_at=conv.created_at,
            ended_at=conv.ended_at,
            last_message=last_msg,
        ))
    return rows


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

    result = await db.execute(select(Conversation).where(Conversation.user_id == current_user.id, Conversation.session_id == session_id))
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

    if conversation.selected_profile == "employee":
        module = ModuleType.EMPLOYEE
    else:
        intent = await intent_classifier_service.classify(message)
        module = intent.module

    if conversation.selected_profile == "support_engineer" and current_user.role not in {UserRole.SUPPORT_ENGINEER, UserRole.ADMIN}:
        raise HTTPException(status_code=403, detail="No tienes permiso para operar como Ingeniero de Soporte")

    if not can_access_module(current_user.role, MODULE_PERM.get(module, "employee_chat")):
        raise HTTPException(status_code=403, detail=f"Sin permiso para módulo: {module.value}")

    conversation.module = module
    conversation.question_count = (conversation.question_count or 0) + 1

    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=message,
        has_image=bool(image_analysis),
        image_gcs_url=image_gcs_url,
        metadata_={"selected_profile": conversation.selected_profile, "question_number": conversation.question_count},
    ))

    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)
        bot_result = await employee_bot_service.generate_response(message, image_analysis=image_analysis, faq_context=faq, db=db)
    elif module == ModuleType.SUPPORT_RAG:
        bot_result = await support_rag_service.generate_response(message, image_analysis=image_analysis)
    else:
        bot_result = await server_monitor_service.analyze_and_respond(message, image_analysis=image_analysis)

    if conversation.question_count >= settings.MAX_QUESTIONS_PER_SESSION:
        bot_result["text"] = f"{bot_result['text']}\n\nHas alcanzado el límite de {settings.MAX_QUESTIONS_PER_SESSION} preguntas para esta sesión. Por control de consumo de IA, esta conversación será finalizada."
        chat_guard_service.finish_conversation(conversation, "question_limit_reached", "ended")

    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=bot_result["text"],
        tokens_used=bot_result.get("tokens_used"),
        response_time_ms=bot_result.get("response_time_ms"),
        metadata_={"sources": bot_result.get("sources"), "knowledge_gap": bot_result.get("knowledge_gap"), "module": module.value},
    ))

    if bot_result.get("escalated_to_aranda"):
        conversation.escalated_to_aranda = True

    if bot_result.get("knowledge_gap"):
        from app.models.knowledge_gap import KnowledgeGap
        existing = (await db.execute(select(KnowledgeGap).where(KnowledgeGap.query == message[:255]))).scalar_one_or_none()
        if existing:
            existing.frequency += 1
            existing.last_seen = datetime.now(timezone.utc)
        else:
            db.add(KnowledgeGap(query=message[:255], module=module.value, user_role=current_user.role.value, avg_confidence=bot_result.get("avg_confidence", 0), last_seen=datetime.now(timezone.utc)))

    await audit_service.log(db, "chat_message_sent", current_user.id, module.value, {"session_id": session_id, "question_count": conversation.question_count, "tokens_used": bot_result.get("tokens_used")})
    await db.commit()

    return ChatMessageResponse(
        response=bot_result["text"],
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=bot_result.get("tokens_used"),
        has_image_analysis=bool(image_analysis),
        escalated_to_aranda=bot_result.get("escalated_to_aranda", False),
        sources=bot_result.get("sources"),
        knowledge_gap=bot_result.get("knowledge_gap", False),
        session_status=conversation.session_status,
        ended_reason=conversation.ended_reason,
        question_count=conversation.question_count or 0,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
    )


@router.post("/session/{session_id}/end")
async def end_session(session_id: str, current_user: User = Depends(require_employee), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.user_id == current_user.id, Conversation.session_id == session_id, Conversation.ended_at.is_(None)))
    conversation = result.scalar_one_or_none()
    if conversation:
        chat_guard_service.finish_conversation(conversation, "user_closed_session", "ended")
        await audit_service.log(db, "chat_session_ended", current_user.id, "chat", {"session_id": session_id, "conversation_id": str(conversation.id)})
        await db.commit()
    return {"message": "Sesión cerrada", "session_id": session_id}
