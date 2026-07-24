from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea el access token normal de BOTIQ para dashboard y API."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_widget_access_token(
    *,
    user_id: str,
    role: str,
    portal_id: str,
    allowed_origin: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Crea un JWT de corta vida exclusivo para el widget embebible.

    El token:
    - no se persiste en localStorage/sessionStorage;
    - solo sirve con purpose=widget_access;
    - queda asociado al portal y al origin autorizados;
    - incluye jti para trazabilidad;
    - expira por defecto en WIDGET_TOKEN_EXPIRE_MINUTES.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.WIDGET_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "purpose": "widget_access",
        "portal_id": portal_id,
        "allowed_origin": allowed_origin,
        "iss": settings.WIDGET_TOKEN_ISSUER,
        "aud": settings.WIDGET_TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now - timedelta(seconds=5),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Valida tokens normales y tokens efímeros del widget.

    Los tokens MFA y cualquier purpose desconocido se rechazan como
    credenciales de sesión. Para widget_access también se verifican issuer,
    audience, portal_id, allowed_origin y jti.
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Los access tokens normales históricos no incluyen aud. Se decodifica
        # primero sin verificar audience y luego se valida de forma explícita
        # solo para purpose=widget_access.
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )

        purpose = payload.get("purpose")
        if purpose == "mfa_challenge":
            raise exc
        if purpose not in {None, "access", "widget_access"}:
            raise exc

        user_id: str = payload.get("sub")
        if not user_id:
            raise exc

        # Conserva exactamente el contrato histórico para access tokens
        # normales; los claims adicionales solo se exponen para el widget.
        if purpose != "widget_access":
            return {
                "user_id": user_id,
                "role": payload.get("role"),
            }

        result = {
            "user_id": user_id,
            "role": payload.get("role"),
            "purpose": "widget_access",
        }

        if purpose == "widget_access":
            if payload.get("iss") != settings.WIDGET_TOKEN_ISSUER:
                raise exc
            if payload.get("aud") != settings.WIDGET_TOKEN_AUDIENCE:
                raise exc

            portal_id = str(payload.get("portal_id") or "").strip()
            allowed_origin = str(payload.get("allowed_origin") or "").strip()
            jti = str(payload.get("jti") or "").strip()
            if not portal_id or not allowed_origin or not jti:
                raise exc

            result.update(
                {
                    "portal_id": portal_id,
                    "allowed_origin": allowed_origin,
                    "jti": jti,
                }
            )

        return result
    except HTTPException:
        raise
    except JWTError:
        raise exc


def generate_refresh_token() -> str:
    """Token opaco de alta entropía para la cookie httpOnly de refresh."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash SHA-256 del refresh token aleatorio antes de guardarlo en DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_mfa_challenge_token(user_id: str) -> str:
    """Token corto que únicamente permite completar el segundo factor."""
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": user_id,
        "purpose": "mfa_challenge",
        "iat": now,
        "exp": now
        + timedelta(minutes=settings.MFA_CHALLENGE_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_mfa_challenge_token(token: str) -> Optional[str]:
    """Devuelve user_id solo si el token corresponde al desafío MFA."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        return None
    if payload.get("purpose") != "mfa_challenge":
        return None
    return payload.get("sub")
