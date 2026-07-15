from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.session import Base


class RefreshToken(Base):
    """
    Refresh tokens de sesión (JWT en cookie httpOnly + este registro en DB).

    No se guarda el token en texto plano: solo su hash SHA-256 (token_hash).
    Esto permite:
    - Revocar sesiones individuales (logout) sin invalidar el SECRET_KEY global.
    - Rotación: cada uso de /auth/refresh revoca el token usado y emite uno nuevo.
    - Trazabilidad básica (user_agent, created_at) sin guardar el secreto real.
    """
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_agent = Column(String(500), nullable=True)

    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > datetime.now(timezone.utc)