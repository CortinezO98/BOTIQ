from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SAEnum, Integer
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
    module = Column(SAEnum(ModuleType), nullable=False, default=ModuleType.EMPLOYEE)
    session_id = Column(String(100), index=True)

    selected_profile = Column(String(50), nullable=True, index=True)  # employee | support_engineer
    session_status = Column(String(30), default="active", index=True)  # active | ended | blocked
    ended_reason = Column(String(255), nullable=True)
    question_count = Column(Integer, default=0)
    out_of_scope_count = Column(Integer, default=0)

    support_network_username = Column(String(150), nullable=True, index=True)
    support_network_validated = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to_aranda = Column(Boolean, default=False)

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
