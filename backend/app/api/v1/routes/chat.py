"""
Endpoint principal del chatbot BOTIQ.
Orquesta los tres módulos: Employee, Support RAG, Server Monitor.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import get_db
from app.api.deps import get_current_user, require_employee
from app.models.user import User
from app.models.conversation import Conversation, Message, ModuleType, MessageRole
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.core.roles import UserRole, can_access_module
from app.modules.employee_bot.service import employee_bot_service
from app.modules.support_rag.service import support_rag_service
from app.modules.server_monitor.service import server_monitor_service
from app.services.vertex.gemini_vision_service import gemini_vision_service

router = APIRouter()


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint principal del chatbot.
    Enruta al módulo correcto según el rol del usuario y el contenido del mensaje.
    """
    # ── 1. Procesar imagen si existe ─────────────────────────────────────────
    image_analysis = None
    if request.image_base64:
        image_result = await gemini_vision_service.analyze_error_screenshot(
            image_base64=request.image_base64,
            mime_type=request.image_mime_type or "image/jpeg",
        )
        image_analysis = image_result.get("description")

    # ── 2. Determinar módulo a usar ───────────────────────────────────────────
    module = _determine_module(request.message, current_user.role)

    # ── 3. Verificar permisos ─────────────────────────────────────────────────
    module_key = _module_to_permission_key(module)
    if not can_access_module(current_user.role, module_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes acceso al módulo {module.value}",
        )

    # ── 4. Obtener o crear conversación ───────────────────────────────────────
    session_id = request.session_id or str(uuid.uuid4())
    conversation = Conversation(
        user_id=current_user.id,
        module=module,
        session_id=session_id,
    )
    db.add(conversation)
    await db.flush()

    # ── 5. Guardar mensaje del usuario ────────────────────────────────────────
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
        has_image=request.image_base64 is not None,
    )
    db.add(user_message)

    # ── 6. Generar respuesta según módulo ─────────────────────────────────────
    result = await _route_to_module(
        module=module,
        message=request.message,
        image_analysis=image_analysis,
        user=current_user,
        db=db,
    )

    # ── 7. Guardar respuesta del bot ──────────────────────────────────────────
    bot_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result["text"],
        tokens_used=result.get("tokens_used"),
        response_time_ms=result.get("response_time_ms"),
        metadata={
            "sources": result.get("sources"),
            "faq_used": result.get("faq_used"),
            "image_analyzed": image_analysis is not None,
        },
    )
    db.add(bot_message)

    # Actualizar si se escaló a Aranda
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


def _determine_module(message: str, user_role: UserRole) -> ModuleType:
    """
    Determina qué módulo usar según el mensaje y el rol.
    Lógica simple de enrutamiento por palabras clave.
    """
    message_lower = message.lower()

    # Palabras clave para servidores
    server_keywords = ["servidor", "server", "caído", "caido", "down", "memoria",
                       "cpu", "disco", "infraestructura", "estado del servidor"]

    # Solo si el usuario tiene acceso a soporte o es admin
    if user_role in [UserRole.SUPPORT_ENGINEER, UserRole.ADMIN]:
        if any(kw in message_lower for kw in server_keywords):
            return ModuleType.SERVER_VALIDATION

        # RAG para ingenieros de soporte
        return ModuleType.SUPPORT_RAG

    return ModuleType.EMPLOYEE


def _module_to_permission_key(module: ModuleType) -> str:
    mapping = {
        ModuleType.EMPLOYEE: "employee_chat",
        ModuleType.SUPPORT_RAG: "support_rag",
        ModuleType.SERVER_VALIDATION: "server_validation",
    }
    return mapping.get(module, "employee_chat")


async def _route_to_module(
    module: ModuleType,
    message: str,
    image_analysis,
    user: User,
    db: AsyncSession,
) -> dict:
    """Enruta la solicitud al servicio de módulo correspondiente."""
    if module == ModuleType.EMPLOYEE:
        faq_context = await employee_bot_service.get_faq_answer(message, db)
        return await employee_bot_service.generate_response(
            user_message=message,
            image_analysis=image_analysis,
            faq_context=faq_context,
            db=db,
        )
    elif module == ModuleType.SUPPORT_RAG:
        return await support_rag_service.generate_response(
            user_message=message,
            image_analysis=image_analysis,
        )
    elif module == ModuleType.SERVER_VALIDATION:
        return await server_monitor_service.analyze_and_respond(
            user_query=message,
            image_analysis=image_analysis,
        )

    # Fallback al módulo de empleados
    return await employee_bot_service.generate_response(user_message=message, db=db)
