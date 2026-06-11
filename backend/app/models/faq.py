"""
Modelo de preguntas frecuentes (FAQ) para el módulo de empleados.
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime, timezone
import uuid

from app.db.session import Base


class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100), nullable=True, index=True)
    tags = Column(ARRAY(String), nullable=True)
    is_active = Column(Boolean, default=True)
    hit_count = Column(Integer, default=0)     # Cuántas veces se respondió esta FAQ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<FAQ: {self.question[:60]}>"
