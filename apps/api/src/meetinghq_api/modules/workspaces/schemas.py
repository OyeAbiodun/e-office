"""Workspace API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSettings(BaseModel):
    """Validated workspace configuration."""

    working_hours: dict[str, list[str]] = Field(default_factory=dict)
    calendar_preferences: dict[str, object] = Field(default_factory=dict)
    meeting_defaults: dict[str, object] = Field(default_factory=dict)
    chat_defaults: dict[str, object] = Field(default_factory=dict)
    governance: dict[str, object] = Field(default_factory=dict)
    retention: dict[str, object] = Field(default_factory=dict)
    permissions: dict[str, object] = Field(default_factory=dict)
    integrations: dict[str, object] = Field(default_factory=dict)


class WorkspaceCreate(BaseModel):
    """Workspace creation request."""

    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    classification: str = Field(default="internal", max_length=40)
    visibility: str = Field(default="members", pattern=r"^(members|private|organization)$")
    data_region: str | None = Field(default=None, max_length=80)


class WorkspaceUpdate(BaseModel):
    """Mutable workspace fields."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    logo_url: str | None = Field(default=None, max_length=2048)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    settings: WorkspaceSettings | None = None
    classification: str | None = Field(default=None, max_length=40)
    visibility: str | None = Field(default=None, pattern=r"^(members|private|organization)$")
    data_region: str | None = Field(default=None, max_length=80)
    owner_id: uuid.UUID | None = None


class WorkspaceResponse(BaseModel):
    """Workspace representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    brand_color: str | None
    classification: str
    visibility: str
    data_region: str | None
    owner_id: uuid.UUID | None
    settings: dict[str, object]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberInput(BaseModel):
    """Workspace access assignment."""

    user_id: uuid.UUID
    role: str = Field(default="member", pattern=r"^(member|administrator|owner)$")


class WorkspaceMemberRoleUpdate(BaseModel):
    """Workspace-local role transition."""

    role: str = Field(pattern=r"^(member|administrator|owner)$")


class WorkspaceMemberResponse(BaseModel):
    """Directory-backed workspace membership."""

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: str
    role: str
    created_at: datetime


class WorkspaceOverview(BaseModel):
    """Real workspace administration projection."""

    workspace: WorkspaceResponse
    team_count: int
    member_count: int
    administrator_count: int
    channel_count: int
    meeting_count: int
    calendar_count: int
    file_count: int
    storage_bytes: int
    app_count: int
    recent_activity: list[dict[str, object]]
    audit_history: list[dict[str, object]]


class WorkspaceIntegrationInput(BaseModel):
    provider: str = Field(pattern=r"^[a-z0-9_-]+$", max_length=80)
    display_name: str = Field(min_length=2, max_length=160)
    enabled: bool = True
    configuration: dict[str, object] = Field(default_factory=dict)


class WorkspaceIntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    provider: str
    display_name: str
    enabled: bool
    configuration: dict[str, object]
    created_at: datetime


class WorkspaceTemplateInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    configuration: dict[str, object] = Field(default_factory=dict)


class WorkspaceTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    configuration: dict[str, object]
    created_at: datetime


class WorkspaceBulkAction(BaseModel):
    workspace_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^(archive|restore)$")


class WorkspaceBulkResult(BaseModel):
    updated_ids: list[uuid.UUID]
    skipped_ids: list[uuid.UUID]
