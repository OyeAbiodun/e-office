"""Authentication HTTP contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from meetinghq_api.modules.auth.infrastructure.passwords import validate_password


class RegisterRequest(BaseModel):
    """Tenant and initial administrator registration."""

    organization_name: str = Field(min_length=2, max_length=160)
    organization_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    workspace_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$", min_length=3, max_length=64)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email identifiers."""
        return str(value).lower()

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        validate_password(value)
        return value


class LoginRequest(BaseModel):
    """Password login request."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)
    device_name: str | None = Field(default=None, max_length=200)


class RefreshRequest(BaseModel):
    """Optional body refresh token for non-browser clients."""

    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    """Authenticated password-change request."""

    current_password: str
    new_password: str = Field(min_length=12, max_length=128)
    confirm_new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        validate_password(value)
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password confirmation does not match")
        return self


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """One-time password reset completion."""

    token: str
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        validate_password(value)
        return value


class VerifyEmailRequest(BaseModel):
    """One-time email verification completion."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Verification delivery request."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic non-sensitive operation response."""

    message: str


class UserResponse(BaseModel):
    """Authenticated identity representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    display_name: str
    avatar_url: str | None
    email_verified: bool
    force_password_change: bool
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    """Successful authentication response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    csrf_token: str
    user: UserResponse


class SessionResponse(BaseModel):
    """Authenticated device session."""

    id: uuid.UUID
    device: str | None
    browser: str | None
    os: str | None
    ip_address: str | None
    last_activity: datetime
    expires_at: datetime
    current: bool
