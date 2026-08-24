"""System health API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

HealthState = Literal["healthy", "degraded", "unavailable", "not_configured"]
RequirementState = Literal["required", "recommended", "optional", "configured"]


class ComponentHealth(BaseModel):
    key: str
    name: str
    category: str
    status: HealthState
    requirement: RequirementState = "required"
    configured: bool = True
    message: str
    latency_ms: float | None = None
    details: dict[str, object] = Field(default_factory=dict)


class QueueHealth(BaseModel):
    pending: int
    failed: int
    delivered: int


class SystemHealthResponse(BaseModel):
    status: HealthState
    score: int
    required_healthy: int
    required_total: int
    checked_at: datetime
    last_updated: datetime
    version: str
    environment: str
    uptime_seconds: int
    components: list[ComponentHealth]
    queue: QueueHealth
    warnings: list[str]
    errors: list[str]
    recommendations: list[str]


class HealthHistoryPoint(BaseModel):
    score: int
    status: str
    checked_at: datetime
    incidents: int
