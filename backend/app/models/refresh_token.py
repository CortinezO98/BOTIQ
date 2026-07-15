from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.session import Base
from app.core.config import settings


class RefreshToken(Base):
    """
    Refresh tokens de sesión (JWT en cookie httpOnly + este registro en DB).

    No se guarda el token en texto plano: solo su hash SHA-256 (token_hash).
    Esto permite:
    - Revocar sesiones individuales (logout) sin invalidar el SECRET_KEY global.
    - Rotación: cada uso de /auth/refresh marca el token como "rotado" y
      emite uno nuevo.

    revoked_at vs rotated_at — dos motivos de invalidación distintos:
    - revoked_at: revocación REAL e inmediata (logout explícito, o
      detección de reuso fuera del período de gracia). Sin excepciones.
    - rotated_at: el token ya se usó una vez para renovar la sesión. Se
      acepta reutilizarlo brevemente (REFRESH_TOKEN_GRACE_SECONDS) para
      absorber ráfagas de peticiones concurrentes que llegan con la MISMA
      cookie todavía no actualizada (varias pestañas del navegador, o
      varias llamadas del frontend disparadas en paralelo que expiran su
      access token casi al mismo tiempo). Sin este margen, la primera en
      llegar rota el token con éxito y todas las demás, que ya habían
      mandado la cookie vieja, quedan rechazadas en cascada — un usuario
      con sesión activa de verdad terminaba viendo 401 en toda la app.
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
    rotated_at = Column(DateTime(timezone=True), nullable=True)
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
        if expires <= datetime.now(timezone.utc):
            return False

        if self.rotated_at is not None:
            rotated = self.rotated_at
            if rotated.tzinfo is None:
                rotated = rotated.replace(tzinfo=timezone.utc)
            grace_deadline = rotated + timedelta(seconds=settings.REFRESH_TOKEN_GRACE_SECONDS)
            if datetime.now(timezone.utc) > grace_deadline:
                return False

        return True