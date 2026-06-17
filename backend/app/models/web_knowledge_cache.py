from datetime import datetime, timezone, timedelta
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class WebKnowledgeCache(Base):
    """
    Conocimiento sugerido generado desde búsqueda web controlada.

    Flujo:
    - BOTIQ lo crea automáticamente como pending cuando internet ayuda a responder.
    - Un admin/soporte lo revisa.
    - Si se aprueba, se convierte en FAQ interna.
    - La próxima vez BOTIQ responde desde esta tabla/FAQ y evita nueva búsqueda web.
    """

    __tablename__ = "web_knowledge_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    question = Column(Text, nullable=False)
    normalized_question = Column(String(500), nullable=False, index=True)

    answer = Column(Text, nullable=False)
    sources = Column(JSONB, nullable=True)  # [{title, link, snippet, source}]
    category = Column(String(120), nullable=True, index=True)
    tags = Column(JSONB, nullable=True)

    confidence = Column(Float, default=0.0)
    status = Column(String(30), default="pending", index=True)  # pending | approved | rejected

    web_search_used = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)

    created_by = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    approved_by = Column(UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by = Column(UUID(as_uuid=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=180),
        index=True,
    )

    faq_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


