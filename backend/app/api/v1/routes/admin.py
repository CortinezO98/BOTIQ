"""
Rutas de administración de usuarios BOTIQ.
Solo accesibles para rol ADMIN.
Permite crear/editar/desactivar usuarios con cualquier rol.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import uuid

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.schemas.user import UserResponse
from app.core.security import hash_password
from app.core.roles import UserRole

router = APIRouter()


# ── Schemas específicos de admin ──────────────────────────────────────────────

class AdminCreateUser(BaseModel):
    """Crear usuario con cualquier rol — solo admin."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.EMPLOYEE


class AdminUpdateUser(BaseModel):
    """Actualizar datos básicos de un usuario."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    password: Optional[str] = Field(None, min_length=8)


class AdminChangeRole(BaseModel):
    """Cambiar el rol de un usuario."""
    role: UserRole


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserResponse],
            summary="Listar todos los usuarios")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201,
             summary="Crear usuario con cualquier rol")
async def create_user(
    data: AdminCreateUser,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Único endpoint que permite crear admins e ingenieros de soporte.
    Requiere token de admin existente.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse,
            summary="Obtener un usuario por ID")
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.put("/users/{user_id}", response_model=UserResponse,
            summary="Actualizar nombre o contraseña de un usuario")
async def update_user(
    user_id: uuid.UUID,
    data: AdminUpdateUser,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if data.full_name:
        user.full_name = data.full_name
    if data.password:
        user.hashed_password = hash_password(data.password)

    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse,
              summary="Cambiar el rol de un usuario")
async def change_role(
    user_id: uuid.UUID,
    data: AdminChangeRole,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    # Un admin no puede bajar su propio rol
    if str(user_id) == str(current_admin.id):
        raise HTTPException(
            status_code=400,
            detail="No puedes cambiar tu propio rol"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.role = data.role
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/disable", response_model=UserResponse,
              summary="Desactivar un usuario")
async def disable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    if str(user_id) == str(current_admin.id):
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/enable", response_model=UserResponse,
              summary="Reactivar un usuario")
async def enable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user
