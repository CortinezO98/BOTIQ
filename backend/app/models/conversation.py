"""
Modelos de conversación y mensajes del chatbot BOTIQ.
Almacenan el historial completo para métricas y auditoría.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from enum import Enum
import uuid

from app.db.session import Base


class ModuleType(str, Enum):
    EMPLOYEE = "employee"
    SUPPORT_RAG = "support_rag"
    SERVER_VALIDATION = "server_validation"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    module = Column(SAEnum(ModuleType), nullable=False)
    session_id = Column(String(100), index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to_aranda = Column(Boolean, default=False)  # ¿Se escaló a Aranda?

    # Relaciones
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation {self.id} [{self.module}]>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    has_image = Column(Boolean, default=False)
    image_gcs_url = Column(String(500), nullable=True)  # URL en Cloud Storage
    tokens_used = Column(Float, nullable=True)          # Tokens consumidos en Vertex AI
    response_time_ms = Column(Float, nullable=True)     # Latencia de respuesta
    metadata = Column(JSONB, nullable=True)             # Datos adicionales del RAG, etc.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relaciones
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.role}: {self.content[:50]}>"
