"""Schemas para el chat."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
from app.models.conversation import ModuleType


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
