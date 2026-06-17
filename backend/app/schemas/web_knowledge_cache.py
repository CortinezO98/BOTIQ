from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class WebKnowledgeCacheResponse(BaseModel):
    id: uuid.UUID
    question: str
    normalized_question: str
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: float = 0.0
    status: str
    usage_count: int = 0
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[uuid.UUID] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    faq_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class WebKnowledgeCacheUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=5)
    answer: Optional[str] = Field(None, min_length=10)
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class WebKnowledgeApproveRequest(BaseModel):
    question: Optional[str] = Field(None, min_length=5)
    answer: Optional[str] = Field(None, min_length=10)
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    create_faq: bool = True


class WebKnowledgeRejectRequest(BaseModel):
    reason: Optional[str] = None
