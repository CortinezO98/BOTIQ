"""
Schemas Pydantic para validación de datos de usuario y autenticación.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import uuid

from app.core.roles import UserRole


# ─── Request Schemas ─────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.EMPLOYEE


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ─── Response Schemas ────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None
