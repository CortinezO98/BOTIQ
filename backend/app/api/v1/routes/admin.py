from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.application_matrix import ApplicationMatrix
from app.models.network_user import NetworkUser
from app.models.user import User
from app.models.web_knowledge_cache import WebKnowledgeCache
from app.schemas.application_matrix import (
    ApplicationMatrixCreate,
    ApplicationMatrixResponse,
    ApplicationMatrixUpdate,
)
from app.schemas.network_user import NetworkUserCreate, NetworkUserResponse, NetworkUserUpdate
from app.schemas.user import AdminChangeRole, AdminCreateUser, AdminUpdateUser, UserResponse
from app.schemas.web_knowledge_cache import WebKnowledgeApproveRequest, WebKnowledgeCacheResponse, WebKnowledgeCacheUpdate, WebKnowledgeRejectRequest
from app.services.audit_service import audit_service
from app.services.web_knowledge_cache_service import web_knowledge_cache_service

router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Usuarios de BOTIQ
# ─────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    data: AdminCreateUser,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await audit_service.log(
        db,
        "user_created",
        current.id,
        "admin",
        {"created_user_email": user.email, "role": user.role.value},
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUpdateUser,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if data.full_name:
        user.full_name = data.full_name
    if data.password:
        user.hashed_password = hash_password(data.password)

    await audit_service.log(
        db,
        "user_updated",
        current.id,
        "admin",
        {"target_user_id": str(user.id), "email": user.email},
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: uuid.UUID,
    data: AdminChangeRole,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    if str(user_id) == str(current.id):
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    old_role = user.role.value
    user.role = data.role
    await audit_service.log(
        db,
        "role_changed",
        current.id,
        "admin",
        {"target_user_id": str(user.id), "old_role": old_role, "new_role": data.role.value},
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
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
async def enable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = True
    await audit_service.log(db, "user_enabled", current.id, "admin", {"target_user_id": str(user.id), "email": user.email})
    await db.commit()
    await db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────
# Usuarios de red para Ingenieros de Soporte
# ─────────────────────────────────────────────────────────────

@router.get("/network-users", response_model=List[NetworkUserResponse])
async def list_network_users(
    q: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
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
async def create_network_user(
    data: NetworkUserCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
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
async def update_network_user(
    network_user_id: uuid.UUID,
    data: NetworkUserUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
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


# ─────────────────────────────────────────────────────────────
# Matriz interna de aplicaciones / URLs / IPs / servidores
# ─────────────────────────────────────────────────────────────

@router.get("/application-matrix", response_model=List[ApplicationMatrixResponse])
async def list_application_matrix(
    q: str = Query(""),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(ApplicationMatrix).order_by(ApplicationMatrix.created_at.desc())
    if active_only:
        stmt = stmt.where(ApplicationMatrix.is_active == True)

    rows = (await db.execute(stmt)).scalars().all()

    if q:
        qn = q.lower().strip()
        rows = [
            r for r in rows
            if qn in (r.app_name or "").lower()
            or qn in (r.portal_name or "").lower()
            or qn in (r.url_pattern or "").lower()
            or qn in (r.ip_address or "").lower()
            or qn in (r.server_name or "").lower()
            or qn in (r.owner_area or "").lower()
            or qn in (r.support_group or "").lower()
        ]

    return rows


@router.post("/application-matrix", response_model=ApplicationMatrixResponse, status_code=201)
async def create_application_matrix_item(
    data: ApplicationMatrixCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    row = ApplicationMatrix(**data.model_dump())
    db.add(row)
    await db.flush()
    await audit_service.log(
        db,
        "application_matrix_created",
        current.id,
        "admin",
        {"app_name": row.app_name, "url_pattern": row.url_pattern, "server_name": row.server_name},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/application-matrix/{item_id}", response_model=ApplicationMatrixResponse)
async def update_application_matrix_item(
    item_id: uuid.UUID,
    data: ApplicationMatrixUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    row = (await db.execute(select(ApplicationMatrix).where(ApplicationMatrix.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Registro de matriz no encontrado")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)

    await audit_service.log(
        db,
        "application_matrix_updated",
        current.id,
        "admin",
        {"item_id": str(row.id), "app_name": row.app_name},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/application-matrix/{item_id}/disable", response_model=ApplicationMatrixResponse)
async def disable_application_matrix_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    row = (await db.execute(select(ApplicationMatrix).where(ApplicationMatrix.id == item_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Registro de matriz no encontrado")

    row.is_active = False
    await audit_service.log(db, "application_matrix_disabled", current.id, "admin", {"item_id": str(row.id)})
    await db.commit()
    await db.refresh(row)
    return row

# ─────────────────────────────────────────────────────────────
# Conocimiento web sugerido / pendiente de aprobación
# ─────────────────────────────────────────────────────────────

@router.get("/web-knowledge-cache", response_model=List[WebKnowledgeCacheResponse])
async def list_web_knowledge_cache(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    q: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await web_knowledge_cache_service.list_items(db, status=status, q=q, limit=limit)


@router.put("/web-knowledge-cache/{item_id}", response_model=WebKnowledgeCacheResponse)
async def update_web_knowledge_cache_item(
    item_id: uuid.UUID,
    data: WebKnowledgeCacheUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    item = (await db.execute(select(WebKnowledgeCache).where(WebKnowledgeCache.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Sugerencia web no encontrada")

    payload = data.model_dump(exclude_unset=True)
    if "question" in payload and payload["question"]:
        item.question = payload["question"]
        item.normalized_question = web_knowledge_cache_service.normalize_question(item.question)
    if "answer" in payload and payload["answer"]:
        item.answer = payload["answer"]
    if "category" in payload:
        item.category = payload["category"]
    if "tags" in payload:
        item.tags = payload["tags"]

    await audit_service.log(db, "web_knowledge_updated", current.id, "admin", {"item_id": str(item.id)})
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/web-knowledge-cache/{item_id}/approve", response_model=WebKnowledgeCacheResponse)
async def approve_web_knowledge_cache_item(
    item_id: uuid.UUID,
    data: WebKnowledgeApproveRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    item = (await db.execute(select(WebKnowledgeCache).where(WebKnowledgeCache.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Sugerencia web no encontrada")

    item = await web_knowledge_cache_service.approve_as_faq(
        db,
        item,
        approved_by=current.id,
        question=data.question,
        answer=data.answer,
        category=data.category,
        tags=data.tags,
        create_faq=data.create_faq,
    )

    await audit_service.log(
        db,
        "web_knowledge_approved",
        current.id,
        "admin",
        {"item_id": str(item.id), "faq_id": str(item.faq_id) if item.faq_id else None},
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/web-knowledge-cache/{item_id}/reject", response_model=WebKnowledgeCacheResponse)
async def reject_web_knowledge_cache_item(
    item_id: uuid.UUID,
    data: WebKnowledgeRejectRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    item = (await db.execute(select(WebKnowledgeCache).where(WebKnowledgeCache.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Sugerencia web no encontrada")

    item = await web_knowledge_cache_service.reject(db, item, rejected_by=current.id, reason=data.reason)
    await audit_service.log(db, "web_knowledge_rejected", current.id, "admin", {"item_id": str(item.id), "reason": data.reason})
    await db.commit()
    await db.refresh(item)
    return item
