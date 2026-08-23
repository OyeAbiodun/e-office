"""Invitation API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from meetinghq_api.modules.invitations.models import InvitationStatus


class InvitationCreate(BaseModel):
    """Organization invitation request."""

    email: EmailStr
    role_name: str = Field(default="Member", max_length=80)


class InvitationAccept(BaseModel):
    """Invitation acceptance request for a new identity."""

    token: str
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$", min_length=3, max_length=64)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)


class InvitationResponse(BaseModel):
    """Invitation representation without its secret."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    role_name: str
    status: InvitationStatus
    expires_at: datetime
    resend_count: int
    created_at: datetime


class InvitationCreated(InvitationResponse):
    """Development-friendly invitation creation result."""

    invitation_token: str
