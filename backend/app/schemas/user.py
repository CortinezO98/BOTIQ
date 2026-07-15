from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import uuid
from app.core.roles import UserRole

class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.EMPLOYEE

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    mfa_enabled: bool = False
    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class AdminCreateUser(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.EMPLOYEE

class AdminUpdateUser(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    password: Optional[str] = Field(None, min_length=8)

class AdminChangeRole(BaseModel):
    role: UserRole


# ── MFA ──────────────────────────────────────────────────────────────────

class MfaChallengeResponse(BaseModel):
    """
    Respuesta de /auth/login cuando el usuario tiene MFA activo: en vez de
    la sesión, entrega un token de desafío de corta vida para /auth/mfa/verify.
    """
    mfa_required: bool = True
    mfa_challenge_token: str


class MfaSetupResponse(BaseModel):
    """Respuesta de /auth/mfa/setup: QR + secreto para carga manual."""
    secret: str
    otpauth_uri: str
    qr_code_base64: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MfaVerifyRequest(BaseModel):
    mfa_challenge_token: str
    code: str = Field(..., min_length=6, max_length=6)


class MfaDisableRequest(BaseModel):
    password: str
    code: str = Field(..., min_length=6, max_length=6)