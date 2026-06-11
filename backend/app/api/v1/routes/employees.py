"""Rutas de empleados — gestión de FAQs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.session import get_db
from app.api.deps import require_employee, require_admin
from app.models.user import User
from app.models.faq import FAQ

router = APIRouter()


@router.get("/faqs")
async def list_faqs(db: AsyncSession = Depends(get_db), _: User = Depends(require_employee)):
    result = await db.execute(select(FAQ).where(FAQ.is_active == True).order_by(FAQ.hit_count.desc()))
    return result.scalars().all()


@router.post("/faqs", status_code=201)
async def create_faq(
    question: str, answer: str, category: str = None,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    faq = FAQ(question=question, answer=answer, category=category)
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}")
async def delete_faq(faq_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")
    faq.is_active = False
    await db.commit()
    return {"message": "FAQ desactivada"}
