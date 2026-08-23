"""Invitation lifecycle endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.invitations.schemas import (
    InvitationAccept,
    InvitationCreate,
    InvitationResponse,
)
from meetinghq_api.modules.invitations.service import InvitationService
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.users.schemas import UserResponse
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/invitations", tags=["invitations"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[InvitationResponse])
async def list_invitations(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.INVITATIONS_READ)],
) -> list[InvitationResponse]:
    return [
        InvitationResponse.model_validate(item)
        for item in await InvitationService(session, settings).list(user.organization_id)
    ]


@router.post("", response_model=InvitationResponse, status_code=201)
async def invite_user(
    body: InvitationCreate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.INVITATIONS_WRITE)],
) -> InvitationResponse:
    invitation = await InvitationService(session, settings).invite(
        user.organization_id, str(body.email), body.role_name, user.id
    )
    return InvitationResponse.model_validate(invitation)


@router.post("/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation(
    invitation_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.INVITATIONS_WRITE)],
) -> InvitationResponse:
    return InvitationResponse.model_validate(
        await InvitationService(session, settings).resend(user.organization_id, invitation_id)
    )


@router.delete("/{invitation_id}", response_model=OperationResponse)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.INVITATIONS_WRITE)],
) -> OperationResponse:
    await InvitationService(session, settings).cancel(user.organization_id, invitation_id)
    return OperationResponse(message="Invitation cancelled")


@router.post("/accept", response_model=UserResponse)
async def accept_invitation(
    body: InvitationAccept, session: Session, settings: AppSettings
) -> UserResponse:
    user = await InvitationService(session, settings).accept(
        body.token, body.username, body.first_name, body.last_name, body.password
    )
    return UserResponse.model_validate(user)
