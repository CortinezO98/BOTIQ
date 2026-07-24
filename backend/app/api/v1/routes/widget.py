from datetime import datetime, timedelta, timezone
import re
import secrets
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter
from app.core.roles import UserRole
from app.core.security import create_widget_access_token, hash_password
from app.core.widget_security import (
    get_widget_portal,
    validate_portal_origin,
    validate_portal_secret,
)
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import audit_service

router = APIRouter()
logger = get_logger(__name__, service="widget_tokens")

_EMAIL_RE = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)


class WidgetTokenRequest(BaseModel):
    """Identidad ya autenticada por el portal corporativo."""

    email: str = Field(..., min_length=5, max_length=255)
    full_name: str = Field(..., min_length=2, max_length=255)
    origin: str = Field(
        ...,
        min_length=8,
        max_length=255,
        description="Origin exacto del portal, sin ruta.",
    )


class WidgetTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: datetime
    portal_id: str
    allowed_origin: str
    widget_url: str
    user: dict


def _normalize_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El correo recibido desde el portal no es válido.",
        )
    return email


def _validate_email_domain(email: str, portal: dict) -> None:
    allowed_domains = portal.get("email_domains") or (
        settings.get_registration_allowed_domains()
    )
    if not allowed_domains:
        return

    domain = email.rsplit("@", 1)[-1].lower()
    if domain not in {item.lower() for item in allowed_domains}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El dominio del usuario no está autorizado para este portal.",
        )


async def _resolve_employee_user(
    *,
    db: AsyncSession,
    email: str,
    full_name: str,
    portal: dict,
) -> tuple[User, bool]:
    user = (
        await db.execute(
            select(User).where(func.lower(User.email) == email)
        )
    ).scalar_one_or_none()

    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La cuenta BOTIQ asociada está desactivada.",
            )
        if user.role != UserRole.EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "El widget externo solo emite sesiones de Empleado. "
                    "Usa una identidad de empleado separada para este portal."
                ),
            )
        return user, False

    if not portal.get("auto_provision", settings.WIDGET_AUTO_PROVISION_USERS):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "El usuario no existe en BOTIQ y el aprovisionamiento "
                "automático está deshabilitado."
            ),
        )

    # La contraseña aleatoria no se entrega ni se registra en logs. La cuenta
    # se usa mediante tokens del portal; un administrador puede asignarle una
    # contraseña posteriormente si también necesita acceso directo a BOTIQ.
    random_unusable_password = secrets.token_urlsafe(48)
    normalized_full_name = " ".join(str(full_name or "").split())
    if len(normalized_full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre recibido desde el portal no es válido.",
        )

    user = User(
        email=email,
        full_name=normalized_full_name,
        hashed_password=hash_password(random_unusable_password),
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user, True


@router.post("/token", response_model=WidgetTokenResponse)
@limiter.limit(settings.WIDGET_TOKEN_RATE_LIMIT)
async def issue_widget_token(
    request: Request,
    response: Response,
    data: WidgetTokenRequest,
    x_botiq_portal_id: str = Header(
        ...,
        alias="X-BOTIQ-Portal-Id",
    ),
    x_botiq_portal_secret: str = Header(
        ...,
        alias="X-BOTIQ-Portal-Secret",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Emite un token efímero mediante intercambio backend a backend.

    Este endpoint debe ser invocado por el BACKEND del portal. La clave
    X-BOTIQ-Portal-Secret nunca debe aparecer en HTML ni JavaScript.
    """
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    response.headers["Pragma"] = "no-cache"

    if not settings.WIDGET_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El widget embebible no está habilitado.",
        )

    portal = get_widget_portal(x_botiq_portal_id)
    validate_portal_secret(portal, x_botiq_portal_secret)
    allowed_origin = validate_portal_origin(portal, data.origin)

    email = _normalize_email(data.email)
    _validate_email_domain(email, portal)

    user, auto_provisioned = await _resolve_employee_user(
        db=db,
        email=email,
        full_name=data.full_name,
        portal=portal,
    )

    expires_delta = timedelta(
        minutes=max(1, int(settings.WIDGET_TOKEN_EXPIRE_MINUTES))
    )
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    access_token = create_widget_access_token(
        user_id=str(user.id),
        role=UserRole.EMPLOYEE.value,
        portal_id=portal["id"],
        allowed_origin=allowed_origin,
        expires_delta=expires_delta,
    )

    await audit_service.log(
        db,
        "widget_token_issued",
        user.id,
        "widget",
        {
            "portal_id": portal["id"],
            "allowed_origin": allowed_origin,
            "expires_in_seconds": int(expires_delta.total_seconds()),
            "auto_provisioned": auto_provisioned,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(user)

    widget_base = settings.WIDGET_PUBLIC_URL.rstrip("/")
    logger.info(
        "widget_token_issued",
        portal_id=portal["id"],
        user_id=str(user.id),
        origin=allowed_origin,
    )

    return WidgetTokenResponse(
        access_token=access_token,
        expires_in=int(expires_delta.total_seconds()),
        expires_at=expires_at,
        portal_id=portal["id"],
        allowed_origin=allowed_origin,
        widget_url=f"{widget_base}/widget.html",
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": UserRole.EMPLOYEE.value,
        },
    )


@router.get("/config")
async def widget_public_config(
    portal_id: Optional[str] = None,
):
    """Configuración pública mínima; nunca expone secretos ni usuarios."""
    if not settings.WIDGET_ENABLED:
        raise HTTPException(status_code=404, detail="Widget no habilitado.")

    configured_ids = {item["id"] for item in settings.get_widget_portals()}
    if portal_id and portal_id not in configured_ids:
        raise HTTPException(status_code=404, detail="Portal no configurado.")

    return {
        "enabled": True,
        "version": "v1",
        "portal_configured": portal_id in configured_ids if portal_id else None,
        "widget_url": f"{settings.WIDGET_PUBLIC_URL.rstrip('/')}/widget.html",
        "loader_url": (
            f"{settings.WIDGET_PUBLIC_URL.rstrip('/')}"
            "/widget/v1/botiq-loader.js"
        ),
        "token_expires_in": settings.WIDGET_TOKEN_EXPIRE_MINUTES * 60,
    }
