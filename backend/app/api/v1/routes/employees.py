"""
Rutas del módulo de empleados — gestión de FAQs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.db.session import get_db
from app.api.deps import require_admin, require_employee
from app.models.user import User
from app.models.faq import FAQ

router = APIRouter()


@router.get("/faqs", tags=["FAQs"])
async def list_faqs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_employee),
):
    """Lista todas las FAQs activas."""
    result = await db.execute(
        select(FAQ).where(FAQ.is_active == True).order_by(FAQ.hit_count.desc())
    )
    return result.scalars().all()


@router.post("/faqs", status_code=status.HTTP_201_CREATED, tags=["FAQs"])
async def create_faq(
    question: str,
    answer: str,
    category: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Crea una nueva FAQ. Solo administradores."""
    faq = FAQ(question=question, answer=answer, category=category)
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}", tags=["FAQs"])
async def delete_faq(
    faq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Desactiva una FAQ. Solo administradores."""
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    faq.is_active = False
    await db.commit()
    return {"message": "FAQ desactivada"}
