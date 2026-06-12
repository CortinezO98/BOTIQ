from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from app.models.conversation import ModuleType, MessageRole


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
    sources: Optional[List[str]] = None
    knowledge_gap: bool = False
    session_status: str = "active"
    ended_reason: Optional[str] = None
    question_count: int = 0
    max_questions: int = 0


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
    support_network_username: Optional[str] = None
    support_network_validated: bool = False
    created_at: datetime
    ended_at: Optional[datetime] = None
    escalated_to_aranda: bool = False

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
    support_network_username: Optional[str] = None
    support_network_validated: bool
    escalated_to_aranda: bool
    created_at: datetime
    ended_at: Optional[datetime] = None
    last_message: Optional[str] = None
