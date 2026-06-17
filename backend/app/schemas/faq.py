from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class FAQCreate(BaseModel):
    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=5)
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class FAQResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    category: Optional[str]
    tags: Optional[List[str]]
    is_active: bool
    hit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

