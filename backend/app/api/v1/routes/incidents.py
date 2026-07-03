"""
Endpoints admin para:
  A. Aprobación de respuestas de IA general
     GET  /api/v1/admin/ai-knowledge-cache          → lista pendientes de fuente "general_ai"
     PATCH /api/v1/admin/ai-knowledge-cache/{id}/approve
     PATCH /api/v1/admin/ai-knowledge-cache/{id}/reject

  B. Alertas de incidentes masivos
     GET  /api/v1/admin/incident-alerts             → alertas abiertas
     PATCH /api/v1/admin/incident-alerts/{id}/acknowledge
     PATCH /api/v1/admin/incident-alerts/{id}/resolve
     GET  /api/v1/dashboard/incident-alerts/count  → contador para badge en navbar

Se registran en api/v1/__init__.py con prefix /admin y /dashboard.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.incident_alert import IncidentAlert
from app.models.user import User
from app.models.web_knowledge_cache import WebKnowledgeCache
from app.services.audit_service import audit_service
from app.services.incident_service import incident_service
from app.services.web_knowledge_cache_service import web_knowledge_cache_service

router = APIRouter()


# ════════════════════════════════════════════════════════════════════════════
# A. Aprobación de respuestas de IA general
# Reutiliza web_knowledge_cache filtrado por source_type = "general_ai"
# ════════════════════════════════════════════════════════════════════════════

class AIKnowledgeApproveRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    create_faq: bool = True


class AIKnowledgeRejectRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/ai-knowledge-cache")
async def list_ai_knowledge(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    q: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Lista respuestas generadas por el general_assistant_service (IA sin fuente interna)
    pendientes de revisión por un admin. Mismo patrón que web_knowledge_cache
    pero filtrado por source_type = 'general_ai'.
    """
    query = (
        select(WebKnowledgeCache)
        .where(
            WebKnowledgeCache.source_type == "general_ai",
            WebKnowledgeCache.status == status,
        )
        .order_by(WebKnowledgeCache.usage_count.desc(), WebKnowledgeCache.created_at.desc())
        .limit(limit)
    )
    if q:
        query = query.where(WebKnowledgeCache.question.ilike(f"%{q}%"))

    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "question": r.question,
            "answer": r.answer,
            "category": r.category,
            "tags": r.tags,
            "confidence": r.confidence,
            "status": r.status,
            "usage_count": r.usage_count,
            "source_type": r.source_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "faq_id": str(r.faq_id) if r.faq_id else None,
        }
        for r in rows
    ]


@router.patch("/ai-knowledge-cache/{item_id}/approve")
async def approve_ai_knowledge(
    item_id: uuid.UUID,
    data: AIKnowledgeApproveRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    item = (await db.execute(
        select(WebKnowledgeCache).where(
            WebKnowledgeCache.id == item_id,
            WebKnowledgeCache.source_type == "general_ai",
        )
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Respuesta de IA no encontrada")

    item = await web_knowledge_cache_service.approve_as_faq(
        db, item,
        approved_by=current.id,
        question=data.question,
        answer=data.answer,
        category=data.category,
        tags=data.tags,
        create_faq=data.create_faq,
    )
    await audit_service.log(db, "ai_knowledge_approved", current.id, "admin",
                            {"item_id": str(item.id), "faq_id": str(item.faq_id) if item.faq_id else None})
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "status": item.status, "faq_id": str(item.faq_id) if item.faq_id else None}


@router.patch("/ai-knowledge-cache/{item_id}/reject")
async def reject_ai_knowledge(
    item_id: uuid.UUID,
    data: AIKnowledgeRejectRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    item = (await db.execute(
        select(WebKnowledgeCache).where(
            WebKnowledgeCache.id == item_id,
            WebKnowledgeCache.source_type == "general_ai",
        )
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Respuesta de IA no encontrada")

    item = await web_knowledge_cache_service.reject(db, item, rejected_by=current.id, reason=data.reason)
    await audit_service.log(db, "ai_knowledge_rejected", current.id, "admin",
                            {"item_id": str(item.id), "reason": data.reason})
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "status": item.status}


# ════════════════════════════════════════════════════════════════════════════
# B. Alertas de incidentes masivos
# ════════════════════════════════════════════════════════════════════════════

class AcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    notes: Optional[str] = None


def _alert_to_dict(a: IncidentAlert) -> dict:
    return {
        "id": str(a.id),
        "application_name": a.application_name,
        "app_or_url": a.app_or_url,
        "category": a.category,
        "severity": a.severity,
        "affected_users_count": a.affected_users_count,
        "status": a.status,
        "recommendation": a.recommendation,
        "first_seen_at": a.first_seen_at.isoformat() if a.first_seen_at else None,
        "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "conversation_ids": a.conversation_ids or [],
        "notes": a.notes,
    }


@router.get("/incident-alerts")
async def list_incident_alerts(
    status: str = Query("open", pattern="^(open|acknowledged|resolved|all)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(IncidentAlert)
    if status != "all":
        query = query.where(IncidentAlert.status == status)
    query = query.order_by(
        IncidentAlert.affected_users_count.desc(),
        IncidentAlert.created_at.desc()
    ).limit(limit)

    rows = (await db.execute(query)).scalars().all()
    return [_alert_to_dict(r) for r in rows]


@router.get("/incident-alerts/count")
async def incident_alerts_count(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Contador rápido para badge en el navbar del admin."""
    from sqlalchemy import func
    count = (await db.execute(
        select(func.count(IncidentAlert.id)).where(IncidentAlert.status == "open")
    )).scalar() or 0
    return {"open": count}


@router.patch("/incident-alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    data: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    alert = await incident_service.acknowledge(db, alert_id, current.id, data.notes)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    await audit_service.log(db, "incident_acknowledged", current.id, "admin",
                            {"alert_id": str(alert_id)})
    await db.commit()
    return _alert_to_dict(alert)


@router.patch("/incident-alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    data: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
):
    alert = await incident_service.resolve(db, alert_id, current.id, data.notes)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    await audit_service.log(db, "incident_resolved", current.id, "admin",
                            {"alert_id": str(alert_id)})
    await db.commit()
    return _alert_to_dict(alert)