from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, EmailStr, Field


class NetworkUserCreate(BaseModel):
    network_username: str = Field(..., min_length=3, max_length=150)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_support_enabled: bool = True
    is_active: bool = True


class NetworkUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_support_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class NetworkUserResponse(BaseModel):
    id: uuid.UUID
    network_username: str
    email: Optional[str]
    full_name: Optional[str]
    is_support_enabled: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
