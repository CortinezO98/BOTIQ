from sqlalchemy import Column, String, Float, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid
from app.db.session import Base

class ServerLog(Base):
    __tablename__ = "server_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_name = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    memory_usage = Column(Float, nullable=True)
    cpu_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    is_healthy = Column(Boolean, default=True)
    raw_data = Column(JSONB, nullable=True)
    queried_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


