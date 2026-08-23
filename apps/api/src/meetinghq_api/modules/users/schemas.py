"""User management and profile contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from meetinghq_api.modules.auth.infrastructure.passwords import validate_password
from meetinghq_api.modules.users.models import UserStatus


class UserProfileUpdate(BaseModel):
    """Self-service profile update."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    timezone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=10)
    notification_preferences: dict[str, object] | None = None


class ProfileCenterUpdate(BaseModel):
    cover_image_url: str | None = Field(default=None, max_length=2048)
    presence: str | None = Field(
        default=None, pattern=r"^(available|busy|do_not_disturb|away|offline)$"
    )
    status_message: str | None = Field(default=None, max_length=240)
    manager_id: uuid.UUID | None = None
    emergency_contact: dict[str, object] | None = None
    email_aliases: list[EmailStr] | None = Field(default=None, max_length=20)
    signature: str | None = Field(default=None, max_length=4000)
    working_hours: dict[str, object] | None = None
    preferences: dict[str, object] | None = None
    connected_accounts: list[dict[str, object]] | None = Field(default=None, max_length=20)


class ProfileCenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    cover_image_url: str | None
    presence: str
    status_message: str | None
    manager_id: uuid.UUID | None
    emergency_contact: dict[str, object]
    email_aliases: list[str]
    signature: str | None
    working_hours: dict[str, object]
    preferences: dict[str, object]
    connected_accounts: list[dict[str, object]]
    mfa_enabled: bool
    storage_used_bytes: int
    license_name: str
    updated_at: datetime


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_at: datetime | None = None


class ApiTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiTokenCreated(ApiTokenResponse):
    token: str


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_data_url: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    code: str | None = Field(default=None, min_length=6, max_length=12)


class MfaRecoveryRegenerateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=12)


class SecurityEventResponse(BaseModel):
    action: str
    created_at: datetime
    ip_address: str | None
    metadata: dict[str, object]


class UserCreate(BaseModel):
    """Administrator-created organization account."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    workspace_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] = Field(min_length=1)
    temporary_password: str | None = Field(default=None, min_length=12, max_length=128)
    send_welcome_email: bool = True

    @field_validator("temporary_password")
    @classmethod
    def _validate_temporary_password(cls, value: str | None) -> str | None:
        if value is not None:
            validate_password(value)
        return value


class UserUpdate(BaseModel):
    """Administrator-editable account fields."""

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    workspace_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)


class UserBulkAction(BaseModel):
    """A validated bulk user lifecycle operation."""

    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^(activate|disable|delete|restore)$")


class TemporaryPasswordResponse(BaseModel):
    """One-time administrator-issued temporary password."""

    temporary_password: str
    force_password_change: bool = True


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    permission_ids: list[uuid.UUID] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    permission_ids: list[uuid.UUID] | None = None


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    resource: str
    action: str
    description: str | None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    system_role: bool
    permissions: list[PermissionResponse]


class UserResponse(BaseModel):
    """Organization user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    display_name: str
    avatar_url: str | None
    phone: str | None
    job_title: str | None
    department: str | None
    location: str | None
    workspace_id: uuid.UUID | None
    team_id: uuid.UUID | None
    status: UserStatus
    email_verified: bool
    force_password_change: bool
    last_login: datetime | None
    timezone: str
    language: str
    notification_preferences: dict[str, object]
    roles: list[RoleResponse]
