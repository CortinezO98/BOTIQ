from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid

from app.db.session import get_db
from app.api.deps import require_employee
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType, MessageRole
from app.schemas.chat import ChatMessageResponse, ConversationItem, MessageItem
from app.core.roles import UserRole, can_access_module
from app.modules.employee_bot.service import employee_bot_service
from app.modules.support_rag.service import support_rag_service
from app.modules.server_monitor.service import server_monitor_service
from app.modules.intent_classifier.service import intent_classifier_service
from app.services.vertex.gemini_vision_service import gemini_vision_service
from app.services.gcs_service import gcs_service

router = APIRouter()

MODULE_PERM = {
    ModuleType.EMPLOYEE: "employee_chat",
    ModuleType.SUPPORT_RAG: "support_rag",
    ModuleType.SERVER_VALIDATION: "server_validation",
}


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


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    session_id = session_id or str(uuid.uuid4())

    image_analysis = None
    image_gcs_url = None

    if image and image.filename:
        img_bytes = await image.read()

        if len(img_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")

        if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail=f"Tipo no soportado: {image.content_type}")

        import base64

        b64 = base64.b64encode(img_bytes).decode()
        image_gcs_url = await gcs_service.upload_image(b64, image.content_type)
        vision_result = await gemini_vision_service.analyze_error_screenshot(b64, image.content_type)
        image_analysis = vision_result.get("description")

    if current_user.role == UserRole.EMPLOYEE:
        module = ModuleType.EMPLOYEE
    else:
        intent = await intent_classifier_service.classify(message)
        module = intent.module

    if not can_access_module(current_user.role, MODULE_PERM.get(module, "employee_chat")):
        raise HTTPException(status_code=403, detail=f"Sin permiso para módulo: {module.value}")

    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
            Conversation.ended_at.is_(None),
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            module=module,
            session_id=session_id,
        )
        db.add(conversation)
        await db.flush()

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
            has_image=bool(image_analysis),
            image_gcs_url=image_gcs_url,
        )
    )

    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)
        bot_result = await employee_bot_service.generate_response(
            user_message=message,
            image_analysis=image_analysis,
            faq_context=faq,
            db=db,
        )
    elif module == ModuleType.SUPPORT_RAG:
        bot_result = await support_rag_service.generate_response(
            user_message=message,
            image_analysis=image_analysis,
        )
    else:
        bot_result = await server_monitor_service.analyze_and_respond(
            user_query=message,
            image_analysis=image_analysis,
        )

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
            },
        )
    )

    if bot_result.get("escalated_to_aranda"):
        conversation.escalated_to_aranda = True

    if bot_result.get("knowledge_gap"):
        try:
            from app.models.knowledge_gap import KnowledgeGap
            from datetime import datetime, timezone

            existing = (
                await db.execute(
                    select(KnowledgeGap).where(KnowledgeGap.query == message[:255])
                )
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
        except Exception as exc:
            print(f"Warning knowledge_gap: {exc}")

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
    )


@router.post("/session/{session_id}/end")
async def end_session(
    session_id: str,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
            Conversation.ended_at.is_(None),
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        conversation.ended_at = datetime.now(timezone.utc)
        await db.commit()

    return {"message": "Sesión cerrada", "session_id": session_id}
