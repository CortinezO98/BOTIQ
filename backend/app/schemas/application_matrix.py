from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field


class ApplicationMatrixCreate(BaseModel):
    app_name: str = Field(..., min_length=2, max_length=255)
    portal_name: Optional[str] = None
    url_pattern: Optional[str] = None
    ip_address: Optional[str] = None
    server_name: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner_area: Optional[str] = None
    support_group: Optional[str] = None
    status_source: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class ApplicationMatrixUpdate(BaseModel):
    app_name: Optional[str] = Field(None, min_length=2, max_length=255)
    portal_name: Optional[str] = None
    url_pattern: Optional[str] = None
    ip_address: Optional[str] = None
    server_name: Optional[str] = None
    environment: Optional[str] = None
    criticality: Optional[str] = None
    owner_area: Optional[str] = None
    support_group: Optional[str] = None
    status_source: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ApplicationMatrixResponse(BaseModel):
    id: uuid.UUID
    app_name: str
    portal_name: Optional[str]
    url_pattern: Optional[str]
    ip_address: Optional[str]
    server_name: Optional[str]
    environment: Optional[str]
    criticality: Optional[str]
    owner_area: Optional[str]
    support_group: Optional[str]
    status_source: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


