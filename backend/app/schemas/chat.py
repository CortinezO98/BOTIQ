from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field

from app.models.conversation import MessageRole, ModuleType


class ChatSessionStartRequest(BaseModel):
    selected_profile: str = Field(..., pattern="^(employee|support_engineer)$")
    network_username: Optional[str] = None


class ChatSessionStartResponse(BaseModel):
    session_id: str
    conversation_id: uuid.UUID
    selected_profile: str
    module_used: ModuleType
    support_network_validated: bool = False
    max_questions: int
    welcome_message: str


class ChatMessageResponse(BaseModel):
    response: str
    session_id: str
    module_used: ModuleType
    conversation_id: uuid.UUID
    tokens_used: Optional[float] = None
    has_image_analysis: bool = False
    escalated_to_aranda: bool = False
    aranda_ticket_id: Optional[str] = None
    ticket_eligible: bool = False
    sources: Optional[List[str]] = None
    knowledge_gap: bool = False
    application_status: Optional[Dict[str, Any]] = None
    session_status: str = "active"
    ended_reason: Optional[str] = None
    question_count: int = 0
    max_questions: int = 0
    # Fuente de la respuesta para mostrar en el frontend (chip de gobierno de
    # IA): "faq" | "rag" | "matrix" | "web_approved" | "web_pending" |
    # "general_ai" | None (respuestas guiadas/directas sin fuente, saludos,
    # confirmaciones de ticket, etc.). Calculado en chat.py a partir de los
    # flags que ya existían en bot_result, antes solo persistidos en DB.
    answer_source: Optional[str] = None
    # Resumen seguro del seguimiento Aranda. Nunca contiene sessionId, credenciales,
    # URLs temporales de adjuntos ni notas privadas filtradas.
    ticket_tracking: Optional[Dict[str, Any]] = None


class ConversationItem(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
    selected_profile: Optional[str] = None
    module: ModuleType
    session_status: str = "active"
    ended_reason: Optional[str] = None
    question_count: int = 0
    out_of_scope_count: int = 0
    resolution_attempts: int = 0
    ticket_eligible: bool = False
    support_network_username: Optional[str] = None
    support_network_validated: bool = False
    detected_url: Optional[str] = None
    detected_ip: Optional[str] = None
    escalated_to_aranda: bool = False
    aranda_ticket_id: Optional[str] = None
    aranda_ticket_status: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageItem(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    has_image: bool = False
    image_gcs_url: Optional[str] = None
    tokens_used: Optional[float] = None
    response_time_ms: Optional[float] = None
    metadata_: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminConversationLogItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
    session_id: Optional[str]
    selected_profile: Optional[str]
    module: ModuleType
    session_status: str
    ended_reason: Optional[str] = None
    question_count: int
    out_of_scope_count: int
    resolution_attempts: int
    ticket_eligible: bool
    support_network_username: Optional[str] = None
    support_network_validated: bool
    detected_url: Optional[str] = None
    detected_ip: Optional[str] = None
    escalated_to_aranda: bool
    aranda_ticket_id: Optional[str] = None
    aranda_ticket_status: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    last_message: Optional[str] = None
