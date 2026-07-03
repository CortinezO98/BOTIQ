from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class IncidentAlert(Base):
    """
    Alerta de posible incidente masivo.

    Se crea automáticamente cuando N usuarios distintos reportan el mismo
    aplicativo/portal en una ventana de tiempo configurable (default: 5 usuarios
    en 15 minutos). Permite al equipo de soporte detectar problemas globales
    antes de recibir avalancha de tickets.

    Estados:
        open         → detectado, pendiente de revisión
        acknowledged → un admin tomó nota
        resolved     → incidente cerrado
    """

    __tablename__ = "incident_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_name = Column(String(255), nullable=True, index=True)
    app_or_url = Column(String(500), nullable=True)
    category = Column(String(80), nullable=True, index=True)

    # low | medium | high | critical
    severity = Column(String(20), nullable=False, default="medium")

    affected_users_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # open | acknowledged | resolved
    status = Column(String(30), nullable=False, default="open", index=True)

    recommendation = Column(Text, nullable=True)
    conversation_ids = Column(JSONB, nullable=True)

    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)