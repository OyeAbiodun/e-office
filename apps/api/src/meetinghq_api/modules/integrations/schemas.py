"""Integration Center API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IntegrationResponse(BaseModel):
    key: str
    name: str
    category: str
    description: str
    auth_type: str
    enabled: bool
    configured: bool
    validated: bool
    health: Literal["healthy", "attention", "disabled"]
    updated_at: datetime | None
    last_tested_at: datetime | None


class IntegrationConfigurationUpdate(BaseModel):
    values: dict[str, object] = Field(min_length=1)


class IntegrationOperationResponse(BaseModel):
    key: str
    configured: bool
    message: str


class IntegrationTestResponse(BaseModel):
    key: str
    status: Literal["healthy", "attention"]
    message: str
    latency_ms: int
    checked_at: datetime


class IntegrationAuditResponse(BaseModel):
    action: str
    status: str
    created_at: datetime
    actor_id: str | None
