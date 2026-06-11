"""
Endpoint principal del chatbot BOTIQ.
CORRECCIONES:
  - Reutiliza conversación existente por session_id
  - Valida permisos después de determinar el módulo
  - Acepta imagen como multipart/form-data O base64 JSON
  - Guarda imagen en GCS antes de analizarla
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
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
from app.modules.intent_classifier.service import intent_classifier_service
from app.services.vertex.gemini_vision_service import gemini_vision_service
from app.services.gcs_service import gcs_service

router = APIRouter()

SERVER_KEYWORDS = [
    "servidor", "server", "caído", "caido", "down", "memoria",
    "cpu", "disco", "infraestructura", "máquina", "ambiente",
    "productivo", "latencia", "lento", "no responde",
]

MODULE_PERMISSION_MAP = {
    ModuleType.EMPLOYEE:          "employee_chat",
    ModuleType.SUPPORT_RAG:       "support_rag",
    ModuleType.SERVER_VALIDATION: "server_validation",
}


# ── Endpoint principal ────────────────────────────────────────────────────────

@router.post("/message", response_model=ChatMessageResponse,
             summary="Enviar mensaje al chatbot")
async def send_message(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    Acepta texto + imagen opcional (multipart/form-data).
    Enruta al módulo correcto según el rol y el intent del mensaje.
    """
    session_id = session_id or str(uuid.uuid4())

    # ── 1. Procesar imagen si existe ────────────────────────────────────────
    image_analysis = None
    image_gcs_url = None

    if image and image.filename:
        image_bytes = await image.read()

        # Validar tamaño (máx 5MB)
        if len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="La imagen no puede superar 5MB"
            )

        # Validar tipo MIME
        allowed_mimes = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if image.content_type not in allowed_mimes:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de imagen no soportado: {image.content_type}"
            )

        import base64
        image_b64 = base64.b64encode(image_bytes).decode()

        # Subir a GCS (temporal, lifecycle 1 día)
        image_gcs_url = await gcs_service.upload_image(image_b64, image.content_type)

        # Analizar con Gemini Vision
        vision_result = await gemini_vision_service.analyze_error_screenshot(
            image_b64, image.content_type
        )
        image_analysis = vision_result.get("description")

    # ── 2. Determinar módulo con clasificador de intent ─────────────────────
    module = await _determine_module_with_intent(message, current_user.role)

    # ── 3. VALIDAR PERMISOS del módulo determinado ──────────────────────────
    permission_key = MODULE_PERMISSION_MAP.get(module, "employee_chat")
    if not can_access_module(current_user.role, permission_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes permiso para acceder al módulo: {module.value}"
        )

    # ── 4. Reutilizar conversación existente o crear nueva ──────────────────
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

    # ── 5. Guardar mensaje del usuario ──────────────────────────────────────
    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=message,
        has_image=image is not None and image.filename is not None,
        image_gcs_url=image_gcs_url,
    ))

    # ── 6. Generar respuesta ─────────────────────────────────────────────────
    bot_result = await _route_to_module(
        module=module,
        message=message,
        image_analysis=image_analysis,
        user=current_user,
        db=db,
    )

    # ── 7. Guardar respuesta del bot ─────────────────────────────────────────
    db.add(Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=bot_result["text"],
        tokens_used=bot_result.get("tokens_used"),
        response_time_ms=bot_result.get("response_time_ms"),
        metadata_={
            "sources": bot_result.get("sources"),
            "faq_used": bot_result.get("faq_used"),
            "image_analyzed": image_analysis is not None,
            "knowledge_gap": bot_result.get("knowledge_gap", False),
            "avg_confidence": bot_result.get("avg_confidence"),
        },
    ))

    if bot_result.get("escalated_to_aranda"):
        conversation.escalated_to_aranda = True

    # Registrar brecha de conocimiento si aplica
    if bot_result.get("knowledge_gap"):
        await _register_knowledge_gap(
            query=message,
            module=module,
            user_role=current_user.role,
            avg_confidence=bot_result.get("avg_confidence", 0),
            db=db,
        )

    await db.commit()

    return ChatMessageResponse(
        response=bot_result["text"],
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=bot_result.get("tokens_used"),
        has_image_analysis=image_analysis is not None,
        escalated_to_aranda=bot_result.get("escalated_to_aranda", False),
        sources=bot_result.get("sources"),
        knowledge_gap=bot_result.get("knowledge_gap", False),
    )


@router.post("/message/json", response_model=ChatMessageResponse,
             summary="Enviar mensaje con imagen en base64 (compatibilidad)")
async def send_message_json(
    request: ChatMessageRequest,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint alternativo que acepta JSON con imagen en base64.
    Para compatibilidad con clientes que no soporten multipart.
    """
    session_id = request.session_id or str(uuid.uuid4())

    image_analysis = None
    image_gcs_url = None

    if request.image_base64:
        image_gcs_url = await gcs_service.upload_image(
            request.image_base64,
            request.image_mime_type or "image/jpeg"
        )
        vision_result = await gemini_vision_service.analyze_error_screenshot(
            request.image_base64,
            request.image_mime_type or "image/jpeg"
        )
        image_analysis = vision_result.get("description")

    module = await _determine_module_with_intent(request.message, current_user.role)

    permission_key = MODULE_PERMISSION_MAP.get(module, "employee_chat")
    if not can_access_module(current_user.role, permission_key):
        raise HTTPException(status_code=403, detail=f"Acceso denegado al módulo: {module.value}")

    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.session_id == session_id,
            Conversation.ended_at.is_(None),
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        conversation = Conversation(user_id=current_user.id, module=module, session_id=session_id)
        db.add(conversation)
        await db.flush()

    db.add(Message(
        conversation_id=conversation.id, role=MessageRole.USER,
        content=request.message, has_image=request.image_base64 is not None,
        image_gcs_url=image_gcs_url,
    ))

    bot_result = await _route_to_module(module, request.message, image_analysis, current_user, db)

    db.add(Message(
        conversation_id=conversation.id, role=MessageRole.ASSISTANT,
        content=bot_result["text"], tokens_used=bot_result.get("tokens_used"),
        response_time_ms=bot_result.get("response_time_ms"),
    ))

    if bot_result.get("escalated_to_aranda"):
        conversation.escalated_to_aranda = True

    await db.commit()

    return ChatMessageResponse(
        response=bot_result["text"],
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=bot_result.get("tokens_used"),
        has_image_analysis=image_analysis is not None,
        escalated_to_aranda=bot_result.get("escalated_to_aranda", False),
        sources=bot_result.get("sources"),
    )


@router.post("/session/{session_id}/end",
             summary="Cerrar una sesión de chat")
async def end_session(
    session_id: str,
    current_user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
):
    """Marca la conversación como finalizada."""
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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _determine_module_with_intent(message: str, role: UserRole) -> ModuleType:
    """
    Determina el módulo usando clasificador híbrido:
    1. Si es empleado → siempre EMPLOYEE
    2. Si es soporte/admin → intent classifier (keywords + Gemini si hay duda)
    """
    if role == UserRole.EMPLOYEE:
        return ModuleType.EMPLOYEE

    # Clasificador de intent para soporte y admin
    intent_result = await intent_classifier_service.classify(message)
    return intent_result.module


async def _route_to_module(
    module: ModuleType,
    message: str,
    image_analysis: Optional[str],
    user: User,
    db: AsyncSession,
) -> dict:
    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)
        return await employee_bot_service.generate_response(
            user_message=message,
            image_analysis=image_analysis,
            faq_context=faq,
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
    # Fallback
    return await employee_bot_service.generate_response(user_message=message, db=db)


async def _register_knowledge_gap(
    query: str,
    module: ModuleType,
    user_role: UserRole,
    avg_confidence: float,
    db: AsyncSession,
):
    """Registra una brecha de conocimiento en la BD para el dashboard."""
    try:
        from app.models.knowledge_gap import KnowledgeGap
        from sqlalchemy import update

        # Buscar si ya existe
        result = await db.execute(
            select(KnowledgeGap).where(KnowledgeGap.query == query[:255])
        )
        gap = result.scalar_one_or_none()

        if gap:
            gap.frequency += 1
            gap.avg_confidence = (gap.avg_confidence + avg_confidence) / 2
            from datetime import datetime, timezone
            gap.last_seen = datetime.now(timezone.utc)
        else:
            from datetime import datetime, timezone
            gap = KnowledgeGap(
                query=query[:255],
                module=module.value,
                user_role=user_role.value,
                frequency=1,
                avg_confidence=avg_confidence,
                last_seen=datetime.now(timezone.utc),
            )
            db.add(gap)
        await db.flush()
    except Exception as e:
        # No bloquear el flujo principal si falla el registro
        print(f"Warning: no se pudo registrar knowledge gap: {e}")
