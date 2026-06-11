from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.schemas.user import UserResponse, AdminCreateUser, AdminUpdateUser, AdminChangeRole
from app.core.security import hash_password

router = APIRouter()


@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201,
             summary="Crear usuario con cualquier rol — solo admin")
async def create_user(data: AdminCreateUser, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = User(email=data.email, full_name=data.full_name,
                hashed_password=hash_password(data.password), role=data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, data: AdminUpdateUser,
                      db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
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


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(user_id: uuid.UUID, data: AdminChangeRole,
                      db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    if str(user_id) == str(current.id):
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.role = data.role
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/disable", response_model=UserResponse)
async def disable_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    if str(user_id) == str(current.id):
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/enable", response_model=UserResponse)
async def enable_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user
