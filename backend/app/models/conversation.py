from datetime import datetime, timezone
from enum import Enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

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

    module = Column(SAEnum(ModuleType), nullable=False, default=ModuleType.EMPLOYEE)
    session_id = Column(String(100), index=True)

    # Flujo conversacional inicial.
    selected_profile = Column(String(50), nullable=True, index=True)  # employee | support_engineer
    session_status = Column(String(30), default="active", index=True)  # active | ended | blocked
    ended_reason = Column(String(255), nullable=True)

    # Controles de consumo y seguridad.
    question_count = Column(Integer, default=0)
    out_of_scope_count = Column(Integer, default=0)
    resolution_attempts = Column(Integer, default=0)
    ticket_eligible = Column(Boolean, default=False)

    # Validación soporte.
    support_network_username = Column(String(150), nullable=True, index=True)
    support_network_validated = Column(Boolean, default=False)

    # Contexto técnico detectado por el bot.
    detected_url = Column(String(500), nullable=True)
    detected_ip = Column(String(100), nullable=True)
    application_status_snapshot = Column(JSONB, nullable=True)

    # Ticket Aranda.
    escalated_to_aranda = Column(Boolean, default=False)
    aranda_ticket_id = Column(String(150), nullable=True, index=True)
    aranda_ticket_status = Column(String(100), nullable=True)
    aranda_ticket_created_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    metadata_ = Column("metadata", JSONB, nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)

    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    has_image = Column(Boolean, default=False)
    image_gcs_url = Column(String(500), nullable=True)

    tokens_used = Column(Float, nullable=True)
    response_time_ms = Column(Float, nullable=True)

    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    conversation = relationship("Conversation", back_populates="messages")


