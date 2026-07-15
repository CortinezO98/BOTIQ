from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets

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
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Un token de desafío MFA (ver create_mfa_challenge_token) NO debe
        # servir como credencial de sesión normal, aunque esté firmado con
        # la misma SECRET_KEY. Los access tokens normales no llevan este
        # claim, así que esto no afecta sesiones ya emitidas.
        if payload.get("purpose") == "mfa_challenge":
            raise exc
        user_id: str = payload.get("sub")
        if user_id is None:
            raise exc
        return {"user_id": user_id, "role": payload.get("role")}
    except JWTError:
        raise exc


def generate_refresh_token() -> str:
    """
    Token opaco de alta entropía (NO es un JWT, no lleva payload legible).
    Se entrega al navegador en una cookie httpOnly y se guarda hasheado en DB.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """
    SHA-256 alcanza aquí (no hace falta bcrypt): el token ya es aleatorio
    de alta entropía, no una contraseña adivinable por fuerza bruta. El
    hash solo evita que una fuga de la tabla refresh_tokens exponga
    sesiones válidas en texto plano.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_mfa_challenge_token(user_id: str) -> str:
    """
    Token de muy corta vida (MFA_CHALLENGE_TOKEN_EXPIRE_MINUTES) que se
    entrega tras un login con password correcto cuando el usuario tiene MFA
    activo. NO es un token de sesión: el claim "purpose" lo marca como
    "mfa_challenge" para que decode_mfa_challenge_token lo rechace si
    alguien intenta reusar un access_token normal (o viceversa) acá.
    """
    to_encode = {
        "sub": user_id,
        "purpose": "mfa_challenge",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.MFA_CHALLENGE_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_mfa_challenge_token(token: str) -> Optional[str]:
    """Devuelve el user_id si el token es válido y tiene purpose=mfa_challenge, si no None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != "mfa_challenge":
        return None
    return payload.get("sub")