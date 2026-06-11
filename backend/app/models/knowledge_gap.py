from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from app.db.session import Base

class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(String(255), nullable=False, index=True)
    module = Column(String(50), nullable=False)
    user_role = Column(String(50), nullable=False)
    frequency = Column(Integer, default=1)
    avg_confidence = Column(Float, default=0.0)
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default="open")
    suggested_document = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
