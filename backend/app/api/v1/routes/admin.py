from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.network_user import NetworkUser
from app.models.user import User
from app.schemas.network_user import NetworkUserCreate, NetworkUserResponse, NetworkUserUpdate
from app.schemas.user import AdminChangeRole, AdminCreateUser, AdminUpdateUser, UserResponse
from app.services.audit_service import audit_service

router = APIRouter()


@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(data: AdminCreateUser, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user = User(email=data.email, full_name=data.full_name, hashed_password=hash_password(data.password), role=data.role)
    db.add(user)
    await db.flush()
    await audit_service.log(db, "user_created", current.id, "admin", {"created_user_email": user.email, "role": user.role.value})
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, data: AdminUpdateUser, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if data.full_name:
        user.full_name = data.full_name
    if data.password:
        user.hashed_password = hash_password(data.password)

    await audit_service.log(db, "user_updated", current.id, "admin", {"target_user_id": str(user.id), "email": user.email})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(user_id: uuid.UUID, data: AdminChangeRole, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    if str(user_id) == str(current.id):
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    old_role = user.role.value
    user.role = data.role
    await audit_service.log(db, "role_changed", current.id, "admin", {"target_user_id": str(user.id), "old_role": old_role, "new_role": data.role.value})
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
    await audit_service.log(db, "user_disabled", current.id, "admin", {"target_user_id": str(user.id), "email": user.email})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/enable", response_model=UserResponse)
async def enable_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = True
    await audit_service.log(db, "user_enabled", current.id, "admin", {"target_user_id": str(user.id), "email": user.email})
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/network-users", response_model=List[NetworkUserResponse])
async def list_network_users(q: str = Query(""), db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(NetworkUser).order_by(NetworkUser.created_at.desc()))
    users = result.scalars().all()

    if q:
        qn = q.lower()
        users = [
            u for u in users
            if qn in (u.network_username or "").lower()
            or qn in (u.email or "").lower()
            or qn in (u.full_name or "").lower()
        ]

    return users


@router.post("/network-users", response_model=NetworkUserResponse, status_code=201)
async def create_network_user(data: NetworkUserCreate, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    username = data.network_username.strip().lower()
    result = await db.execute(select(NetworkUser).where(NetworkUser.network_username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El usuario de red ya existe")

    network_user = NetworkUser(
        network_username=username,
        email=str(data.email).lower() if data.email else None,
        full_name=data.full_name,
        is_support_enabled=data.is_support_enabled,
        is_active=data.is_active,
    )
    db.add(network_user)
    await db.flush()
    await audit_service.log(db, "network_user_created", current.id, "admin", {"network_username": username})
    await db.commit()
    await db.refresh(network_user)
    return network_user


@router.put("/network-users/{network_user_id}", response_model=NetworkUserResponse)
async def update_network_user(network_user_id: uuid.UUID, data: NetworkUserUpdate, db: AsyncSession = Depends(get_db), current: User = Depends(require_admin)):
    result = await db.execute(select(NetworkUser).where(NetworkUser.id == network_user_id))
    network_user = result.scalar_one_or_none()
    if not network_user:
        raise HTTPException(status_code=404, detail="Usuario de red no encontrado")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "email" and value:
            value = str(value).lower()
        setattr(network_user, field, value)

    await audit_service.log(db, "network_user_updated", current.id, "admin", {"network_username": network_user.network_username})
    await db.commit()
    await db.refresh(network_user)
    return network_user
