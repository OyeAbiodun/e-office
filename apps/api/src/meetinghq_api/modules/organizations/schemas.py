"""Organization API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from meetinghq_api.modules.organizations.models import (
    OrganizationStatus,
    OrganizationUnitType,
)


class OrganizationSettings(BaseModel):
    """Validated organization configuration."""

    business_hours: dict[str, list[str]] = Field(default_factory=dict)
    week_start_day: int = Field(default=1, ge=0, le=6)
    meeting_defaults: dict[str, object] = Field(default_factory=dict)
    password_policy: dict[str, object] = Field(default_factory=dict)
    session_timeout_minutes: int = Field(default=1440, ge=15)
    default_theme: str = Field(default="system", pattern="^(light|dark|system)$")


class OrganizationUpdate(BaseModel):
    """Mutable organization profile fields."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    logo_url: str | None = Field(default=None, max_length=2048)
    timezone: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    default_language: str | None = Field(default=None, max_length=10)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    status: OrganizationStatus | None = None
    settings: OrganizationSettings | None = None


class OrganizationCreate(BaseModel):
    """New tenant request."""

    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)


class OrganizationResponse(BaseModel):
    """Organization representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    status: OrganizationStatus
    timezone: str
    country: str | None
    default_language: str
    brand_color: str
    settings: dict[str, object]
    created_at: datetime
    updated_at: datetime


class OrganizationUnitInput(BaseModel):
    """Department, branch, or location mutation."""

    parent_id: uuid.UUID | None = None
    unit_type: OrganizationUnitType
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    manager_id: uuid.UUID | None = None
    status: str = Field(default="active", pattern=r"^(active|inactive)$")
    address: dict[str, object] = Field(default_factory=dict)
    timezone: str | None = Field(default=None, max_length=64)
    working_hours: dict[str, object] = Field(default_factory=dict)


class OrganizationUnitResponse(OrganizationUnitInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DepartmentDetailResponse(OrganizationUnitResponse):
    employee_count: int
    team_count: int
    manager_name: str | None = None
    recent_activity: list[dict[str, object]] = Field(default_factory=list)


class OrganizationPolicyUpdate(BaseModel):
    """Validated policy category payload."""

    values: dict[str, object]


class OrganizationOverview(BaseModel):
    """Live enterprise administration summary."""

    organization: OrganizationResponse
    member_count: int
    active_member_count: int
    workspace_count: int
    team_count: int
    pending_invitation_count: int
    department_count: int
    branch_count: int
    location_count: int
    administrators: list[dict[str, object]]
    recent_activity: list[dict[str, object]]
    audit_history: list[dict[str, object]]
