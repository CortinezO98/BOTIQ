"""
Schemas Pydantic para el módulo de chat del chatbot BOTIQ.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.models.conversation import ModuleType, MessageRole


# ─── Request ─────────────────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image_base64: Optional[str] = None     # Imagen en base64 (opcional)
    image_mime_type: Optional[str] = None  # "image/jpeg", "image/png", etc.


# ─── Response ────────────────────────────────────────────────────────────────

class ChatMessageResponse(BaseModel):
    response: str
    session_id: str
    module_used: ModuleType
    conversation_id: uuid.UUID
    tokens_used: Optional[float] = None
    has_image_analysis: bool = False
    escalated_to_aranda: bool = False
    sources: Optional[List[str]] = None   # Fuentes RAG usadas


class MessageHistory(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    has_image: bool

    class Config:
        from_attributes = True


class ConversationHistory(BaseModel):
    conversation_id: uuid.UUID
    messages: List[MessageHistory]
    module: ModuleType
    created_at: datetime
