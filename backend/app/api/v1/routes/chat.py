"""Endpoint principal del chatbot BOTIQ."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import get_db
from app.api.deps import require_employee
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType, MessageRole
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.core.roles import UserRole, can_access_module
from app.modules.employee_bot.service import employee_bot_service
from app.modules.support_rag.service import support_rag_service
from app.modules.server_monitor.service import server_monitor_service
from app.services.vertex.gemini_vision_service import gemini_vision_service

router = APIRouter()

SERVER_KEYWORDS = ["servidor", "server", "caído", "caido", "down", "memoria", "cpu", "disco", "infraestructura"]


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    # 1. Analizar imagen si existe
    image_analysis = None
    if request.image_base64:
        vision_result = await gemini_vision_service.analyze_error_screenshot(
            request.image_base64, request.image_mime_type or "image/jpeg"
        )
        image_analysis = vision_result.get("description")

    # 2. Determinar módulo
    module = _determine_module(request.message, current_user.role)
    session_id = request.session_id or str(uuid.uuid4())

    # 3. Crear conversación
    conversation = Conversation(user_id=current_user.id, module=module, session_id=session_id)
    db.add(conversation)
    await db.flush()

    # 4. Guardar mensaje usuario
    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
        has_image=request.image_base64 is not None,
    ))

    # 5. Generar respuesta
    result = await _route_to_module(module, request.message, image_analysis, current_user, db)

    # 6. Guardar respuesta bot
    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result["text"],
        tokens_used=result.get("tokens_used"),
        response_time_ms=result.get("response_time_ms"),
    ))

    if result.get("escalated_to_aranda"):
        conversation.escalated_to_aranda = True

    await db.commit()

    return ChatMessageResponse(
        response=result["text"],
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=result.get("tokens_used"),
        has_image_analysis=image_analysis is not None,
        escalated_to_aranda=result.get("escalated_to_aranda", False),
        sources=result.get("sources"),
    )


def _determine_module(message: str, role: UserRole) -> ModuleType:
    msg = message.lower()
    if role in [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN]:
        if any(kw in msg for kw in SERVER_KEYWORDS):
            return ModuleType.SERVER_VALIDATION
        return ModuleType.SUPPORT_RAG
    return ModuleType.EMPLOYEE


async def _route_to_module(module, message, image_analysis, user, db):
    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)
        return await employee_bot_service.generate_response(
            user_message=message, image_analysis=image_analysis, faq_context=faq, db=db
        )
    elif module == ModuleType.SUPPORT_RAG:
        return await support_rag_service.generate_response(
            user_message=message, image_analysis=image_analysis
        )
    elif module == ModuleType.SERVER_VALIDATION:
        return await server_monitor_service.analyze_and_respond(
            user_query=message, image_analysis=image_analysis
        )
    return await employee_bot_service.generate_response(user_message=message, db=db)
