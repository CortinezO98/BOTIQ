from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.session import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.core.roles import UserRole
from app.schemas.user import (
    UserRegister,
    UserResponse,
    TokenResponse,
    MfaChallengeResponse,
    MfaSetupResponse,
    MfaConfirmRequest,
    MfaVerifyRequest,
    MfaDisableRequest,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    create_mfa_challenge_token,
    decode_mfa_challenge_token,
)
from app.core import mfa as mfa_core
from app.core.rate_limit import limiter
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

IS_PRODUCTION = settings.ENVIRONMENT.lower() == "production"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/v1/auth")


async def _issue_refresh_token(db: AsyncSession, user_id, user_agent: Optional[str]) -> str:
    raw_token = generate_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(user_agent or "")[:500],
    )
    db.add(record)
    await db.flush()
    return raw_token


async def _complete_login(db: AsyncSession, response: Response, user: User, request: Request) -> TokenResponse:
    """Emite tokens de sesión reales. Se llama al final del login normal
    (sin MFA) o al final de /auth/mfa/verify (con MFA)."""
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = await _issue_refresh_token(db, user.id, request.headers.get("user-agent"))
    await db.commit()
    _set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Registro público — solo crea empleados",
)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    normalized_email = data.email.lower()

    allowed_domains = settings.get_registration_allowed_domains()
    if allowed_domains:
        email_domain = normalized_email.split("@")[-1]
        if email_domain not in allowed_domains:
            raise HTTPException(
                status_code=403,
                detail="El registro público solo está habilitado para correos corporativos.",
            )

    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = User(
        email=normalized_email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=UserRole.EMPLOYEE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=None)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    normalized_email = form.username.lower()
    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    if user.mfa_enabled:
        # Password correcto, pero falta el segundo factor. No se setea
        # ninguna cookie de sesión todavía.
        challenge_token = create_mfa_challenge_token(str(user.id))
        return MfaChallengeResponse(mfa_challenge_token=challenge_token)

    return await _complete_login(db, response, user, request)


@router.post("/mfa/verify", response_model=TokenResponse)
@limiter.limit(settings.MFA_VERIFY_RATE_LIMIT)
async def mfa_verify(
    request: Request,
    response: Response,
    data: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    user_id = decode_mfa_challenge_token(data.mfa_challenge_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token de desafío inválido o expirado. Inicia sesión de nuevo.")

    user = await db.get(User, user_id)
    if not user or not user.is_active or not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=401, detail="No se pudo completar la verificación MFA.")

    secret = mfa_core.decrypt_secret(user.mfa_secret_encrypted)
    if not secret or not mfa_core.verify_code(secret, data.code):
        raise HTTPException(status_code=401, detail="Código incorrecto.")

    return await _complete_login(db, response, user, request)


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Sin sesión activa para renovar")

    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()

    if not record or not record.is_valid():
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Sesión expirada, inicia sesión nuevamente")

    user = await db.get(User, record.user_id)
    if not user or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    record.revoked_at = datetime.now(timezone.utc)
    new_refresh_token = await _issue_refresh_token(db, user.id, request.headers.get("user-agent"))
    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    await db.commit()

    _set_auth_cookies(response, access_token, new_refresh_token)
    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        record = result.scalar_one_or_none()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            await db.commit()

    _clear_auth_cookies(response)
    return {"message": "Sesión cerrada"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# ── MFA: enrolamiento y baja ────────────────────────────────────────────
# Requieren sesión activa (get_current_user) — no son parte del flujo de
# login sin autenticar, a diferencia de /mfa/verify.

@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera un secreto nuevo y lo guarda cifrado, pero NO activa MFA todavía
    (mfa_enabled sigue False hasta /mfa/confirm). Si se llama de nuevo antes
    de confirmar, reemplaza el secreto pendiente anterior.
    """
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="El MFA ya está activo en esta cuenta.")

    secret = mfa_core.generate_secret()
    current_user.mfa_secret_encrypted = mfa_core.encrypt_secret(secret)
    await db.commit()

    otpauth_uri = mfa_core.build_otpauth_uri(secret, current_user.email)
    qr_base64 = mfa_core.generate_qr_code_base64(otpauth_uri)

    return MfaSetupResponse(secret=secret, otpauth_uri=otpauth_uri, qr_code_base64=qr_base64)


@router.post("/mfa/confirm", response_model=UserResponse)
async def mfa_confirm(
    data: MfaConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="El MFA ya está activo en esta cuenta.")
    if not current_user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="Primero debes iniciar el enrolamiento con /mfa/setup.")

    secret = mfa_core.decrypt_secret(current_user.mfa_secret_encrypted)
    if not secret or not mfa_core.verify_code(secret, data.code):
        raise HTTPException(status_code=401, detail="Código incorrecto. Verifica la hora de tu dispositivo e intenta de nuevo.")

    current_user.mfa_enabled = True
    current_user.mfa_enrolled_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/mfa/disable", response_model=UserResponse)
async def mfa_disable(
    data: MfaDisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Requiere password Y código TOTP vigente (defensa en profundidad:
    ninguno de los dos solos alcanza para apagar el segundo factor)."""
    if not current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="El MFA no está activo en esta cuenta.")

    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    secret = mfa_core.decrypt_secret(current_user.mfa_secret_encrypted or "")
    if not secret or not mfa_core.verify_code(secret, data.code):
        raise HTTPException(status_code=401, detail="Código incorrecto.")

    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_enrolled_at = None
    await db.commit()
    await db.refresh(current_user)
    return current_user