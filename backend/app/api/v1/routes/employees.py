from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.db.session import get_db
from app.api.deps import require_employee, require_admin
from app.models.user import User
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate, FAQResponse

router = APIRouter()


@router.get("/faqs", response_model=List[FAQResponse])
async def list_faqs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_employee),
):
    result = await db.execute(
        select(FAQ)
        .where(FAQ.is_active == True)
        .order_by(FAQ.hit_count.desc(), FAQ.created_at.desc())
    )
    return result.scalars().all()


@router.post("/faqs", response_model=FAQResponse, status_code=201)
async def create_faq(
    data: FAQCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    faq = FAQ(
        question=data.question,
        answer=data.answer,
        category=data.category,
        tags=data.tags,
    )
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: uuid.UUID,
    data: FAQUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()

    if not faq:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)

    await db.commit()
    await db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}")
async def delete_faq(
    faq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()

    if not faq:
        raise HTTPException(status_code=404, detail="FAQ no encontrada")

    faq.is_active = False
    await db.commit()
    return {"message": "FAQ desactivada", "faq_id": str(faq_id)}


