from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.session import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import UserRegister, UserResponse, TokenResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.roles import UserRole
from app.core.rate_limit import limiter
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

IS_PRODUCTION = settings.ENVIRONMENT.lower() == "production"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    SameSite=Lax alcanza acá: localhost:5180 -> localhost:8002 es cross-origin
    (puerto distinto) pero mismo "site" (mismo host), y en producción nginx
    sirve todo bajo el mismo dominio. secure=True solo en producción (ahí sí
    hay HTTPS real vía nginx); en dev por http no se puede exigir Secure.

    El refresh token queda restringido a /api/v1/auth (path) para que el
    navegador NO lo mande en cada request a la API — solo en login/refresh/logout.
    """
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


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Registro público — solo crea empleados",
)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    normalized_email = data.email.lower()
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


@router.post("/login", response_model=TokenResponse)
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

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = await _issue_refresh_token(db, user.id, request.headers.get("user-agent"))
    await db.commit()

    _set_auth_cookies(response, access_token, refresh_token)

    # access_token sigue en el body por compatibilidad con Swagger/Postman/scripts.
    # El navegador ya no necesita guardarlo: la sesión vive en las cookies httpOnly.
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Renueva la sesión usando el refresh token de la cookie httpOnly.
    Rotación: el token usado se revoca y se emite uno nuevo en cada llamada,
    así un refresh token robado deja de servir apenas el dueño real lo use.
    """
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