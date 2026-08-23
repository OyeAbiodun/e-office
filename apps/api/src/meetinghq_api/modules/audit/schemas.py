"""Audit Center response contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditRecordResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    user_id: uuid.UUID | None
    user_name: str
    action: str
    category: str
    resource: str
    resource_id: uuid.UUID | None
    request_id: str | None
    ip_address: str | None
    browser: str | None
    device: str | None
    metadata: dict[str, object]
    created_at: datetime


class AuditPageResponse(BaseModel):
    items: list[AuditRecordResponse]
    total: int
    next_cursor: str | None
    categories: list[str]
    actions: list[str]


class AuditFilters(BaseModel):
    search: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, max_length=80)
    action: str | None = Field(default=None, max_length=120)
    user_id: uuid.UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
