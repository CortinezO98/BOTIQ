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