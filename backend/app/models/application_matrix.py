from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class ApplicationMatrix(Base):
    """
    Matriz interna de aplicaciones/portales/URLs/IPs/servidores.

    Es insumo interno de BOTIQ:
    - El usuario no consulta la tabla directamente.
    - El bot la usa para relacionar una URL o aplicativo con servidor, IP,
      ambiente, criticidad y fuente de estado.
    """

    __tablename__ = "application_matrix"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    app_name = Column(String(255), nullable=False, index=True)
    portal_name = Column(String(255), nullable=True, index=True)
    url_pattern = Column(String(500), nullable=True, index=True)
    ip_address = Column(String(100), nullable=True, index=True)
    server_name = Column(String(255), nullable=True, index=True)

    environment = Column(String(80), nullable=True)       # producción, pruebas, contingencia...
    criticality = Column(String(50), nullable=True)       # baja, media, alta, crítica
    owner_area = Column(String(255), nullable=True)
    support_group = Column(String(255), nullable=True)

    status_source = Column(String(255), nullable=True)    # nombre del tablero/API/origen
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


