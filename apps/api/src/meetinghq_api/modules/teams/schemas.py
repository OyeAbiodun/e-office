"""Team API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from meetinghq_api.modules.teams.models import TeamMemberRole, TeamVisibility


class TeamCreate(BaseModel):
    """Team creation request."""

    workspace_id: uuid.UUID
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=2048)
    banner_url: str | None = Field(default=None, max_length=2048)
    color: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=80)
    visibility: TeamVisibility = TeamVisibility.PUBLIC
    classification: str = Field(default="internal", max_length=40)


class TeamUpdate(BaseModel):
    """Mutable team fields."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=80)
    visibility: TeamVisibility | None = None
    avatar_url: str | None = Field(default=None, max_length=2048)
    banner_url: str | None = Field(default=None, max_length=2048)
    classification: str | None = Field(default=None, max_length=40)
    settings: dict[str, object] | None = None


class TeamResponse(BaseModel):
    """Team representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    color: str
    icon: str | None
    avatar_url: str | None
    banner_url: str | None
    classification: str
    owner_id: uuid.UUID | None
    settings: dict[str, object]
    visibility: TeamVisibility
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TeamMemberCreate(BaseModel):
    """Team join or member-add request."""

    user_id: uuid.UUID
    role: TeamMemberRole = TeamMemberRole.MEMBER


class TeamMemberResponse(BaseModel):
    """Team membership representation."""

    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    role: TeamMemberRole
    joined_at: datetime


class TeamMemberRoleUpdate(BaseModel):
    """Team membership role transition."""

    role: TeamMemberRole


class TransferOwnershipRequest(BaseModel):
    """Team ownership transfer request."""

    user_id: uuid.UUID


class TeamOverview(BaseModel):
    team: TeamResponse
    owner_count: int
    administrator_count: int
    member_count: int
    guest_count: int
    channel_count: int
    meeting_count: int
    upcoming_meeting_count: int
    calendar_count: int
    file_count: int
    storage_bytes: int
    wiki_count: int
    note_count: int
    app_count: int
    active_member_count: int
    open_action_count: int
    announcement_count: int
    health_score: int
    recent_activity: list[dict[str, object]]
    recent_conversations: list[dict[str, object]]
    upcoming_meetings: list[dict[str, object]]


class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    channel_kind: str = Field(
        default="standard",
        pattern=r"^(standard|private|announcement|read_only)$",
    )
    visibility: str = Field(default="members", pattern=r"^(members|private)$")
    moderation_enabled: bool = False
    read_only: bool = False


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    moderation_enabled: bool | None = None
    read_only: bool | None = None
    settings: dict[str, object] | None = None


class ChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    channel_kind: str
    visibility: str
    moderation_enabled: bool
    read_only: bool
    favorite: bool
    pinned: bool
    archived_at: datetime | None
    message_count: int
    member_count: int
    last_activity: datetime | None


class ChannelPreferenceUpdate(BaseModel):
    favorite: bool | None = None
    pinned: bool | None = None


class TeamDocumentInput(BaseModel):
    document_type: str = Field(pattern=r"^(wiki|note)$")
    title: str = Field(min_length=2, max_length=240)
    content: str = Field(default="", max_length=100000)


class TeamDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class TeamIntegrationInput(BaseModel):
    provider: str = Field(pattern=r"^[a-z0-9_-]+$", max_length=80)
    display_name: str = Field(min_length=2, max_length=160)
    enabled: bool = True
    configuration: dict[str, object] = Field(default_factory=dict)


class TeamIntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    display_name: str
    enabled: bool
    configuration: dict[str, object]
    created_at: datetime


class TeamBulkMemberAction(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^(remove|make_member|make_manager)$")


class TeamBulkResult(BaseModel):
    updated_ids: list[uuid.UUID]
    skipped_ids: list[uuid.UUID]
