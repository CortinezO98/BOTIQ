from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
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
from app.services.application_matrix_service import application_matrix_service
from app.services.application_status_service import application_status_service
from app.services.aranda_service import aranda_service
from app.services.audit_service import audit_service
from app.services.chat_guard_service import chat_guard_service
from app.services.conversation_flow_service import FlowDecision, conversation_flow_service
from app.services.gcs_service import gcs_service
from app.services.vertex.gemini_vision_service import gemini_vision_service
from app.services.web_search_service import web_search_service
from app.services.web_knowledge_cache_service import web_knowledge_cache_service
from app.services.routing_policy_service import routing_policy_service
from app.services.general_assistant_service import general_assistant_service

router = APIRouter()

MODULE_PERM = {
    ModuleType.EMPLOYEE: "employee_chat",
    ModuleType.SUPPORT_RAG: "support_rag",
    ModuleType.SERVER_VALIDATION: "server_validation",
}


def _welcome_message(profile: str, support_validated: bool = False) -> str:
    if profile == "support_engineer":
        return (
            "Hola, soy BOTIQ, tu asistente técnico de soporte."
            + (" Tu usuario de red fue validado correctamente." if support_validated else "")
            + "\n\nCuéntame qué necesitas revisar. Puedo apoyarte con procedimientos, preguntas frecuentes, "
            "base de conocimiento, aplicativos, servidores, URLs, IPs, errores técnicos, imágenes de incidentes "
            "y contexto para atención de casos."
        )

    return (
        "Hola, soy BOTIQ, tu asistente virtual corporativo.\n\n"
        "Estoy aquí para ayudarte. Cuéntame qué está pasando con tu equipo, aplicativo, portal, archivo, "
        "impresora, correo, VPN, URL o servicio corporativo, y validaré la información disponible para orientarte."
    )


async def _classify_support_module(message: str) -> ModuleType:
    intent = await intent_classifier_service.classify(message)
    return intent.module


# Cuántos mensajes previos (usuario + asistente) se reenvían como historial a
# Gemini en las respuestas de RAG. Más alto = mejor continuidad conversacional
# pero más tokens consumidos en cada turno. 6 mensajes ≈ 3 intercambios.
RAG_HISTORY_MAX_MESSAGES = 6
# Tope de caracteres por mensaje de historial, para que una respuesta larga
# anterior no infle el prompt de todos los turnos siguientes.
RAG_HISTORY_MAX_CHARS_PER_MESSAGE = 600


async def _load_rag_history(db: AsyncSession, conversation_id: uuid.UUID) -> List[Dict]:
    """
    Carga los últimos turnos YA PERSISTIDOS de la conversación, para dar
    continuidad a Gemini en las respuestas de RAG (p. ej. "dame el paso a
    paso" referido a la respuesta anterior).

    Antes, support_rag_service.generate_response() se llamaba sin `history`,
    así que cada mensaje se procesaba de forma aislada y el modelo no tenía
    forma de saber a qué se refería un mensaje corto de seguimiento.

    Se llama ANTES de agregar el mensaje actual a la sesión de BD, para no
    duplicarlo (el mensaje actual ya se envía aparte como prompt).
    """
    rows = (
        await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
            )
            .order_by(desc(Message.created_at))
            .limit(RAG_HISTORY_MAX_MESSAGES)
        )
    ).scalars().all()

    history: List[Dict] = []
    for row in reversed(rows):  # orden cronológico ascendente
        role = "model" if row.role == MessageRole.ASSISTANT else "user"
        content = (row.content or "")[:RAG_HISTORY_MAX_CHARS_PER_MESSAGE]
        if content:
            history.append({"role": role, "content": content})
    return history


def _compose_app_status_message(status: dict, matrix_result: Optional[dict] = None) -> str:
    if not status and not matrix_result:
        return ""

    matrix_text = ""
    if matrix_result and matrix_result.get("found"):
        app = matrix_result.get("application") or {}
        matrix_text = (
            "Según la matriz interna de aplicaciones:\n"
            f"- Aplicativo: {app.get('app_name') or 'N/A'}\n"
            f"- Portal: {app.get('portal_name') or 'N/A'}\n"
            f"- Servidor asociado: {app.get('server_name') or 'N/A'}\n"
            f"- Ambiente: {app.get('environment') or 'N/A'}\n"
            f"- Criticidad: {app.get('criticality') or 'N/A'}\n"
        )

    if not status:
        return matrix_text

    state = str(status.get("status") or "unknown").lower()
    service = status.get("service_name") or status.get("name") or "el servicio consultado"
    msg = status.get("message") or ""

    if state in {"down", "failed", "error", "critical", "offline"}:
        status_text = (
            f"Validé el estado de {service} y aparece con estado **{state}**. "
            f"{msg}\n\n"
            "Este comportamiento puede requerir escalamiento si el error persiste o impacta a varios usuarios."
        )
    elif state in {"degraded", "warning", "slow"}:
        status_text = (
            f"Validé el estado de {service} y aparece con degradación o advertencia (**{state}**). "
            f"{msg}\n\n"
            "Puede existir intermitencia. Recomiendo validar alcance, hora del evento y evidencia."
        )
    elif state in {"up", "ok", "healthy", "online"}:
        status_text = (
            f"Validé el estado de {service} y aparece operativo (**{state}**). "
            f"{msg}\n\n"
            "Si el problema continúa, revisemos credenciales, VPN, caché del navegador, permisos o el error exacto."
        )
    else:
        status_text = f"Consulté el estado de {service}, pero la respuesta fue indeterminada: {status}"

    return f"{matrix_text}\n{status_text}".strip()


def _compose_unified_answer(
    profile: str,
    decision: FlowDecision,
    faq: Optional[Dict],
    rag_result: Optional[Dict],
    status_reply: str,
    matrix_result: Optional[Dict],
    image_analysis: Optional[str],
) -> Dict:
    """
    Une FAQ + RAG + estado interno + análisis de imagen.
    Evita respuestas secas y registra brechas cuando no hay conocimiento.
    """
    parts: List[str] = []
    sources: List[str] = []
    tokens_used = 0
    response_time_ms = 0
    knowledge_gap = False

    if status_reply:
        parts.append(status_reply)

    if image_analysis:
        parts.append(
            "Analicé la captura adjunta y la usaré como evidencia/contexto del caso.\n"
            f"Resumen visual: {image_analysis[:700]}"
        )

    if faq:
        if profile == "support_engineer":
            parts.append(
                "Según las preguntas frecuentes disponibles:\n\n"
                f"**P:** {faq['question']}\n\n"
                f"**R:** {faq['answer']}"
            )
        else:
            parts.append(
                "Encontré una respuesta relacionada en nuestras preguntas frecuentes:\n\n"
                f"{faq['answer']}"
            )

    if rag_result:
        tokens_used += rag_result.get("tokens_used") or 0
        response_time_ms += rag_result.get("response_time_ms") or 0
        sources.extend(rag_result.get("sources") or [])

        rag_text = (rag_result.get("text") or "").strip()
        rag_failed = bool(rag_result.get("knowledge_gap")) or rag_text.lower().startswith("error ia:")

        if not rag_failed:
            if profile == "support_engineer":
                parts.append(
                    "Según la base de conocimiento corporativa:\n\n"
                    f"{rag_text}"
                )
            else:
                parts.append(
                    "Según la base de conocimiento disponible, te recomiendo:\n\n"
                    f"{rag_text}"
                )
        else:
            knowledge_gap = True

    if not parts:
        knowledge_gap = True
        if profile == "support_engineer":
            parts.append(
                "No encontré una respuesta exacta en FAQs ni en la base de conocimiento.\n\n"
                "Registraré esta brecha de conocimiento para revisión del administrador. "
                "Mientras tanto, valida aplicativo/URL/IP, error exacto, alcance, hora del evento y evidencia antes de escalar."
            )
        else:
            parts.append(
                "No encontré información suficiente en la base de conocimiento para resolverlo con seguridad.\n\n"
                "Para ayudarte mejor, indícame: aplicativo o URL, error exacto, si te pasa solo a ti o a varios usuarios, "
                "y adjunta una captura si la tienes."
            )

    text = "\n\n---\n\n".join(parts).strip()

    return {
        "text": text,
        "tokens_used": tokens_used,
        "response_time_ms": response_time_ms,
        "sources": list({s for s in sources if s}),
        "knowledge_gap": knowledge_gap,
        "faq_used": faq is not None,
        "matrix_used": bool(matrix_result and matrix_result.get("found")),
    }


async def _apply_approved_web_knowledge(
    bot_result: Dict,
    message: str,
    profile: str,
    db: AsyncSession,
) -> Dict:
    """
    Antes de consultar internet, revisa si ya existe conocimiento web aprobado.
    Si existe, responde desde base interna y NO consume Google Custom Search.
    """
    if not bot_result.get("knowledge_gap"):
        return bot_result

    approved = await web_knowledge_cache_service.find_approved(
        db,
        message,
        min_score=settings.WEB_KNOWLEDGE_APPROVED_MIN_SCORE,
    )
    if not approved:
        return bot_result

    prefix = (
        "Encontré una respuesta aprobada en la base interna de conocimiento sugerido:\n\n"
        if profile != "support_engineer"
        else "Encontré conocimiento web previamente aprobado por el administrador:\n\n"
    )

    bot_result["text"] = prefix + approved["answer"]
    bot_result["knowledge_gap"] = False
    bot_result["internal_knowledge_gap"] = False
    bot_result["web_cache_used"] = True
    bot_result["web_cache_id"] = approved["id"]
    bot_result["sources"] = list({*(bot_result.get("sources") or []), "Conocimiento web aprobado"})
    return bot_result


async def _apply_web_fallback(
    bot_result: Dict,
    message: str,
    image_analysis: Optional[str],
    profile: str,
    db: AsyncSession,
    current_user: User,
) -> Dict:
    """
    Consulta internet solo como fallback cuando FAQ/RAG/matriz/estado no dan respuesta suficiente.

    Si internet ayuda:
    - responde al usuario,
    - mantiene trazabilidad de brecha interna,
    - registra automáticamente una sugerencia en web_knowledge_cache con estado pending.
    """
    if not bot_result.get("knowledge_gap") or not settings.WEB_SEARCH_ENABLED:
        if settings.DEBUG:
            print(
                f"[WEB_FALLBACK] no ejecutado | knowledge_gap={bot_result.get('knowledge_gap')} "
                f"WEB_SEARCH_ENABLED={settings.WEB_SEARCH_ENABLED}"
            )
        return bot_result

    can_use, used_today, daily_limit = await web_knowledge_cache_service.can_use_web_today(db)
    if not can_use:
        bot_result["web_search"] = {
            "enabled": True,
            "used": False,
            "reason": f"Límite diario de búsqueda web alcanzado ({used_today}/{daily_limit}).",
            "results": [],
        }
        bot_result["text"] = (
            f"{bot_result.get('text') or ''}\n\n"
            f"Además, el límite diario de búsqueda web está alcanzado ({used_today}/{daily_limit}), "
            "por lo que continuaré con la información interna disponible. "
            "Indícame el error exacto, aplicativo/URL, alcance y una captura si la tienes."
        ).strip()
        return bot_result

    web_result = await web_search_service.search(message)
    web_result["daily_usage"] = {"used_today": used_today + (1 if web_result.get("used") else 0), "daily_limit": daily_limit}

    if settings.DEBUG:
        print(
            f"[WEB_FALLBACK] búsqueda | enabled={web_result.get('enabled')} "
            f"used={web_result.get('used')} api_configured={web_search_service.is_enabled()} "
            f"allowed={web_search_service.is_allowed_query(message)} "
            f"results={len(web_result.get('results') or [])} reason={web_result.get('reason')}"
        )

    if not web_result.get("used") or not web_result.get("results"):
        bot_result["web_search"] = web_result
        return bot_result

    web_context = web_search_service.format_for_prompt(web_result)
    answer = await web_knowledge_cache_service.build_answer_from_web(
        question=message,
        web_context=web_context,
        image_analysis=image_analysis,
        profile=profile,
    )

    intro = (
        "No encontré una guía interna exacta, pero encontré referencias técnicas públicas que pueden ayudar. "
        "Usaré esta información como orientación general, no como política interna oficial.\n\n"
    )
    if profile == "support_engineer":
        intro = (
            "No encontré una coincidencia interna exacta en FAQs/base de conocimiento. "
            "Como apoyo técnico, consulté referencias públicas generales.\n\n"
        )

    generated_text = answer.get("text", "")

    pending_note = (
        "\n\n---\n\n"
        "Registraré esta consulta como conocimiento sugerido pendiente de aprobación. "
        "Si un administrador la aprueba, BOTIQ la usará como FAQ interna en futuras consultas y no necesitará buscar nuevamente en internet."
    )

    bot_result["text"] = intro + generated_text + pending_note
    bot_result["tokens_used"] = (bot_result.get("tokens_used") or 0) + (answer.get("tokens_used") or 0)
    bot_result["response_time_ms"] = (bot_result.get("response_time_ms") or 0) + (answer.get("response_time_ms") or 0)
    bot_result["internal_knowledge_gap"] = True
    bot_result["knowledge_gap"] = False
    bot_result["web_used"] = True
    bot_result["web_search"] = web_result

    if settings.WEB_KNOWLEDGE_AUTO_REGISTER:
        item = await web_knowledge_cache_service.register_pending(
            db,
            question=message,
            answer=generated_text,
            sources=web_result.get("results") or [],
            created_by=current_user.id,
            confidence=0.68,
        )
        bot_result["web_knowledge_cache_id"] = str(item.id)
        bot_result["web_knowledge_status"] = item.status

    return bot_result


async def _apply_general_ai_fallback(
    bot_result: Dict,
    message: str,
    image_analysis: Optional[str],
    profile: str,
    is_general_tech_route: bool,
    history: Optional[List[Dict]],
) -> Dict:
    """
    Último eslabón de la cadena: si NADA más respondió (ni FAQ, ni RAG interno,
    ni conocimiento web aprobado, ni búsqueda web — porque está deshabilitada,
    sin resultados, cupo agotado o la consulta no calificó para salir a
    internet), y la pregunta es de ofimática/tecnología GENERAL (no interna),
    Gemini responde con su propio conocimiento, dejando explícito que es
    orientación general y no un procedimiento validado por IQ.

    Restricción deliberada: NUNCA se activa para preguntas internas/mixtas
    (is_general_tech_route=False). Para esas, inventar una respuesta sin
    ninguna fuente real sería más riesgoso que admitir que no se encontró
    información, porque Gemini no tiene cómo conocer aplicativos, portales
    o políticas internas de IQ.
    """
    if not bot_result.get("knowledge_gap"):
        return bot_result
    if not is_general_tech_route:
        return bot_result
    if not settings.GENERAL_AI_FALLBACK_ENABLED:
        return bot_result

    answer = await general_assistant_service.build_general_answer(
        question=message,
        image_analysis=image_analysis,
        history=history,
    )

    if not answer.get("success", True):
        return bot_result

    generated_text = (answer.get("text") or "").strip()
    if not generated_text:
        return bot_result

    intro = (
        "No encontré una guía interna ni referencias web para esto, pero puedo orientarte con "
        "conocimiento general de la herramienta (no es un procedimiento validado por IQ):\n\n"
        if profile != "support_engineer"
        else "Sin coincidencia interna ni resultado de búsqueda web. Como apoyo, esto es "
        "conocimiento general de la herramienta, no política interna de IQ:\n\n"
    )

    bot_result["text"] = intro + generated_text
    bot_result["tokens_used"] = (bot_result.get("tokens_used") or 0) + (answer.get("tokens_used") or 0)
    bot_result["response_time_ms"] = (bot_result.get("response_time_ms") or 0) + (answer.get("response_time_ms") or 0)
    bot_result["internal_knowledge_gap"] = True
    bot_result["knowledge_gap"] = False
    bot_result["general_ai_used"] = True
    return bot_result


async def _register_knowledge_gap(
    db: AsyncSession,
    message: str,
    module: ModuleType,
    current_user: User,
    avg_confidence: float = 0.0,
):
    from app.models.knowledge_gap import KnowledgeGap

    query = message[:255]
    existing = (
        await db.execute(select(KnowledgeGap).where(KnowledgeGap.query == query))
    ).scalar_one_or_none()

    if existing:
        existing.frequency += 1
        existing.last_seen = datetime.now(timezone.utc)
        existing.avg_confidence = avg_confidence
    else:
        db.add(
            KnowledgeGap(
                query=query,
                module=module.value,
                user_role=current_user.role.value,
                avg_confidence=avg_confidence,
                last_seen=datetime.now(timezone.utc),
                suggested_document="Revisar FAQs, base de conocimiento o matriz de aplicaciones.",
            )
        )


def _build_aranda_subject(conversation: Conversation, decision: FlowDecision) -> str:
    slots = decision.slots or {}
    target = (
        slots.get("app_or_url")
        or slots.get("url")
        or slots.get("ip")
        or conversation.detected_url
        or conversation.detected_ip
        or "Caso de soporte"
    )
    return f"BOTIQ - {decision.case_type} - {target}"[:180]


def _build_direct_response_payload(
    text: str,
    conversation: Conversation,
    module: ModuleType,
    session_id: str,
) -> ChatMessageResponse:
    return ChatMessageResponse(
        response=text,
        session_id=session_id,
        module_used=module,
        conversation_id=conversation.id,
        tokens_used=0,
        session_status=conversation.session_status,
        ended_reason=conversation.ended_reason,
        question_count=conversation.question_count or 0,
        max_questions=settings.MAX_QUESTIONS_PER_SESSION,
        ticket_eligible=bool(conversation.ticket_eligible),
        aranda_ticket_id=conversation.aranda_ticket_id,
    )


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
            "flow": "guided_support_v2",
            "case": {},
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
    """Normaliza fechas de filtros: asegura tz UTC y hace date_to inclusivo."""
    if date_from and date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=timezone.utc)
    if date_to:
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)
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
            msg.content for msg in sorted(
                conv.messages,
                key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc),
            )
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

        return _build_direct_response_payload(
            guard.final_message or "Consulta no permitida.",
            conversation,
            conversation.module,
            session_id,
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

    if conversation.selected_profile == "support_engineer":
        if current_user.role not in {UserRole.SUPPORT_ENGINEER, UserRole.ADMIN}:
            raise HTTPException(status_code=403, detail="No tienes permiso para operar como Ingeniero de Soporte.")
        module = await _classify_support_module(message)
    else:
        # Empleado usa flujo guiado + base de conocimiento + FAQs + estado interno.
        module = ModuleType.EMPLOYEE

    if not can_access_module(current_user.role, MODULE_PERM.get(module, "employee_chat")):
        raise HTTPException(status_code=403, detail=f"Sin permiso para módulo: {module.value}")

    conversation.module = module
    conversation.question_count = (conversation.question_count or 0) + 1

    decision = conversation_flow_service.analyze(conversation, message, image_analysis=image_analysis)
    conversation.metadata_ = conversation_flow_service.merge_case_metadata(conversation.metadata_, decision)

    # Se carga ANTES de agregar el mensaje actual a la sesión, para que el
    # historial no incluya (duplicado) el propio mensaje que se está procesando.
    rag_history = await _load_rag_history(db, conversation.id)

    detected_url = chat_guard_service.extract_url(message) or decision.slots.get("url")
    detected_ip = chat_guard_service.extract_ip(message) or decision.slots.get("ip")

    if detected_url:
        conversation.detected_url = detected_url
    if detected_ip:
        conversation.detected_ip = detected_ip

    # Matriz interna: relaciona URL/IP/aplicativo con servidor, ambiente y criticidad.
    matrix_result = await application_matrix_service.lookup(
        db,
        url=detected_url,
        ip=detected_ip,
        query=message,
    )

    if matrix_result.get("found"):
        app = matrix_result.get("application") or {}
        if not conversation.detected_url and app.get("url_pattern"):
            conversation.detected_url = app["url_pattern"]
        if not conversation.detected_ip and app.get("ip_address"):
            conversation.detected_ip = app["ip_address"]

        # Completa slots con datos de la matriz.
        slots = dict(decision.slots or {})
        slots.setdefault("app_or_url", app.get("app_name") or app.get("portal_name") or app.get("url_pattern"))
        slots.setdefault("url", app.get("url_pattern"))
        slots.setdefault("ip", app.get("ip_address"))
        decision.slots = slots
        conversation.metadata_ = conversation_flow_service.merge_case_metadata(conversation.metadata_, decision)

    routing_decision = routing_policy_service.classify_message(
        message,
        profile=conversation.selected_profile or "employee",
        has_url=bool(detected_url),
        has_ip=bool(detected_ip),
        matrix_found=bool(matrix_result.get("found")),
        case_type=decision.case_type,
    )

    # Si el flujo necesita datos mínimos, primero pregunta y NO quema tokens de RAG/Gemini innecesariamente.
    # EXCEPCIÓN: si el enrutador clasificó la consulta como ofimática general (Excel, Word,
    # Outlook, etc. sin señales internas), NO pedimos aplicativo/URL ni cortamos el turno;
    # dejamos que el flujo continúe hasta FAQ → web-cache → búsqueda web controlada.
    is_general_tech_route = routing_decision.get("intent_family") in {"general_tech", "general_tech_support"}

    if decision.direct_response and decision.intent not in {"ticket_confirmation"} and not is_general_tech_route:
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
                    "flow_decision": decision.__dict__,
                    "matrix_result": matrix_result,
                    "routing_decision": routing_decision,
                },
            )
        )
        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=decision.direct_response,
                metadata_={"guided_question": True, "flow_decision": decision.__dict__},
            )
        )
        await audit_service.log(
            db,
            "chat_guided_question",
            current_user.id,
            module.value,
            {"session_id": session_id, "case_type": decision.case_type, "missing_slots": decision.missing_slots},
        )
        await db.commit()
        return _build_direct_response_payload(decision.direct_response, conversation, module, session_id)

    explicit_ticket_request = chat_guard_service.asks_for_ticket(message) or decision.intent == "ticket_confirmation"

    # Creación estricta de ticket Aranda.
    if explicit_ticket_request:
        can_ticket, reason = conversation_flow_service.can_escalate_to_aranda(
            conversation,
            decision,
            explicit_request=True,
        )
        if not can_ticket:
            db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message, metadata_={"ticket_requested": True, "flow_decision": decision.__dict__}))
            db.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=reason, metadata_={"ticket_denied": True}))
            await audit_service.log(db, "aranda_ticket_denied", current_user.id, "chat", {"session_id": session_id, "reason": reason})
            await db.commit()
            return _build_direct_response_payload(reason, conversation, module, session_id)

        description = aranda_service.build_ticket_description(conversation, message)
        ticket_result = await aranda_service.create_ticket(
            conversation=conversation,
            current_user=current_user,
            subject=_build_aranda_subject(conversation, decision),
            description=description,
            application_status=conversation.application_status_snapshot,
        )
        aranda_service.mark_ticket_result(conversation, ticket_result)
        conversation.metadata_ = conversation_flow_service.merge_case_metadata(
            conversation.metadata_,
            decision,
            pending_ticket_confirmation=False,
        )

        db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message, metadata_={"ticket_requested": True, "flow_decision": decision.__dict__}))
        db.add(Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=ticket_result["message"], metadata_={"ticket_result": ticket_result}))
        await audit_service.log(db, "aranda_ticket_requested", current_user.id, "chat", {"session_id": session_id, "result": ticket_result})
        await db.commit()

        return ChatMessageResponse(
            response=ticket_result["message"],
            session_id=session_id,
            module_used=module,
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

    app_status = None
    app_status_text = ""

    should_check_status = (
        routing_decision.get("use_status", False)
        and (
            decision.should_check_status
            or bool(detected_url or detected_ip)
            or chat_guard_service.asks_about_url_or_service(message)
            or bool(matrix_result.get("found"))
        )
    )

    if should_check_status:
        app_status = await application_status_service.lookup(
            url=conversation.detected_url or detected_url,
            ip=conversation.detected_ip or detected_ip,
            query=message,
        )
        conversation.application_status_snapshot = app_status
        app_status_text = application_status_service.format_for_prompt(app_status)

    matrix_text = application_matrix_service.format_for_prompt(matrix_result)
    status_reply = _compose_app_status_message(app_status, matrix_result)

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
                "matrix_result": matrix_result,
                "flow_decision": decision.__dict__,
                "routing_decision": routing_decision,
            },
        )
    )

    faq = None
    rag_result = None
    bot_result = None

    enriched_message = message
    internal_context_parts = []

    if matrix_text:
        internal_context_parts.append(matrix_text)
    if app_status_text:
        internal_context_parts.append(app_status_text)
    if decision.slots:
        internal_context_parts.append(f"Datos recolectados del caso: {decision.slots}")

    if internal_context_parts:
        enriched_message = f"{message}\n\nInformación interna consultada por BOTIQ:\n" + "\n\n".join(internal_context_parts)

    # Empleado: primero FAQ/cache; RAG solo si el enrutador lo autoriza.
    # Ingeniero: RAG técnico cuando aplica, pero se omite para ofimática general sin señales internas.
    if module == ModuleType.EMPLOYEE:
        faq = await employee_bot_service.get_faq_answer(message, db)

        if routing_decision.get("use_rag", True):
            rag_result = await support_rag_service.generate_response(
                enriched_message, image_analysis=image_analysis, history=rag_history
            )
        else:
            rag_result = {
                "text": "RAG omitido por política de enrutamiento para ahorrar tokens y evitar fuentes internas irrelevantes.",
                "sources": [],
                "avg_confidence": 0,
                "best_confidence": 0,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
                "skipped_by_routing": True,
            }

        bot_result = _compose_unified_answer(
            profile="employee",
            decision=decision,
            faq=faq,
            rag_result=rag_result,
            status_reply=status_reply,
            matrix_result=matrix_result,
            image_analysis=image_analysis,
        )
    elif module == ModuleType.SUPPORT_RAG:
        faq = await employee_bot_service.get_faq_answer(message, db)

        if routing_decision.get("use_rag", True):
            rag_result = await support_rag_service.generate_response(
                enriched_message, image_analysis=image_analysis, history=rag_history
            )
        else:
            rag_result = {
                "text": "RAG omitido por política de enrutamiento para ahorrar tokens y evitar fuentes internas irrelevantes.",
                "sources": [],
                "avg_confidence": 0,
                "best_confidence": 0,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
                "skipped_by_routing": True,
            }

        bot_result = _compose_unified_answer(
            profile="support_engineer",
            decision=decision,
            faq=faq,
            rag_result=rag_result,
            status_reply=status_reply,
            matrix_result=matrix_result,
            image_analysis=image_analysis,
        )
    else:
        server_result = await server_monitor_service.analyze_and_respond(enriched_message, image_analysis=image_analysis)
        bot_result = {
            "text": f"{status_reply}\n\n{server_result.get('text', '')}".strip(),
            "tokens_used": server_result.get("tokens_used"),
            "response_time_ms": server_result.get("response_time_ms"),
            "sources": [],
            "knowledge_gap": False,
            "faq_used": False,
            "matrix_used": bool(matrix_result.get("found")),
        }

    bot_result = await _apply_approved_web_knowledge(
        bot_result=bot_result,
        message=message,
        profile=conversation.selected_profile or "employee",
        db=db,
    )

    bot_result = await _apply_web_fallback(
        bot_result=bot_result,
        message=message,
        image_analysis=image_analysis,
        profile=conversation.selected_profile or "employee",
        db=db,
        current_user=current_user,
    )

    bot_result = await _apply_general_ai_fallback(
        bot_result=bot_result,
        message=message,
        image_analysis=image_analysis,
        profile=conversation.selected_profile or "employee",
        is_general_tech_route=is_general_tech_route,
        history=rag_history,
    )

    if app_status:
        bot_result["application_status"] = app_status

    # Cuenta intentos de solución cuando BOTIQ usó una fuente real.
    used_resolution_source = bool(
        app_status
        or faq
        or (rag_result and not rag_result.get("knowledge_gap") and not rag_result.get("skipped_by_routing"))
        or matrix_result.get("found")
        or image_analysis
    )
    if used_resolution_source:
        chat_guard_service.mark_resolution_attempt(conversation)

    if bot_result.get("knowledge_gap") or bot_result.get("internal_knowledge_gap"):
        await _register_knowledge_gap(
            db,
            message,
            module,
            current_user,
            avg_confidence=(rag_result or {}).get("avg_confidence", 0),
        )

    # Ofrece ticket solo si ya hay señales fuertes y datos mínimos. No crea ticket automático.
    if conversation_flow_service.should_offer_ticket(conversation, decision, app_status):
        conversation.ticket_eligible = True
        offer = conversation_flow_service.build_ticket_offer_message(decision)
        bot_result["text"] = f"{bot_result['text']}\n\n---\n\n{offer}"
        conversation.metadata_ = conversation_flow_service.merge_case_metadata(
            conversation.metadata_,
            decision,
            pending_ticket_confirmation=True,
        )

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
                "faq_used": bot_result.get("faq_used"),
                "matrix_used": bot_result.get("matrix_used"),
                "web_used": bot_result.get("web_used", False),
                "web_search": bot_result.get("web_search"),
                "web_cache_used": bot_result.get("web_cache_used", False),
                "web_cache_id": bot_result.get("web_cache_id"),
                "web_knowledge_cache_id": bot_result.get("web_knowledge_cache_id"),
                "web_knowledge_status": bot_result.get("web_knowledge_status"),
                "internal_knowledge_gap": bot_result.get("internal_knowledge_gap", False),
                "module": module.value,
                "application_status": app_status,
                "matrix_result": matrix_result,
                "resolution_attempts": conversation.resolution_attempts,
                "ticket_eligible": conversation.ticket_eligible,
                "flow_decision": decision.__dict__,
                "routing_decision": routing_decision,
            },
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
            "case_type": decision.case_type,
            "matrix_found": matrix_result.get("found"),
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