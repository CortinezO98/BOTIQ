from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.models.conversation import ModuleType, MessageRole


class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image_base64: Optional[str] = None
    image_mime_type: Optional[str] = None


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


class ConversationItem(BaseModel):
    id: uuid.UUID
    session_id: Optional[str] = None
    module: ModuleType
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
    created_at: datetime

    model_config = {"from_attributes": True}
