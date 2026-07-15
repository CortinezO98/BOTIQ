"""
core/mfa.py — MFA por TOTP (Google Authenticator, Authy, etc.)

Responsabilidades:
- Cifrar/descifrar el secreto TOTP en reposo (nunca se guarda en texto
  plano en la base de datos).
- Generar un secreto nuevo + código QR para enrolamiento.
- Verificar códigos de 6 dígitos contra el secreto de un usuario.

La clave de cifrado (Fernet) se deriva de SECRET_KEY con SHA-256 + base64,
no de un secreto nuevo, para no agregar otra variable de entorno crítica
que alguien tenga que recordar rotar. Esto significa que rotar SECRET_KEY
invalida todos los secretos MFA ya enrolados (los usuarios tendrían que
re-enrolar) — es un trade-off aceptado, documentado acá.
"""
from __future__ import annotations

import base64
import hashlib
import io

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    # Fernet exige una clave de 32 bytes url-safe-base64. Derivamos una
    # determinística a partir de SECRET_KEY con SHA-256.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(raw_secret: str) -> str:
    return _fernet().encrypt(raw_secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str | None:
    try:
        return _fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # SECRET_KEY cambió desde que se enroló, o el dato está corrupto.
        return None


def generate_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_uri(secret: str, account_email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_email, issuer_name=settings.MFA_ISSUER_NAME)


def generate_qr_code_base64(otpauth_uri: str) -> str:
    """Devuelve un PNG en base64, listo para <img src="data:image/png;base64,...">."""
    img = qrcode.make(otpauth_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def verify_code(secret: str, code: str) -> bool:
    """
    valid_window=1: acepta el código del intervalo de 30s actual, el
    anterior y el siguiente (tolerancia de reloj de ~30-60s), estándar
    en implementaciones TOTP para no ser demasiado estricto con relojes
    de celular ligeramente desincronizados.
    """
    if not code or not code.isdigit() or len(code) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)