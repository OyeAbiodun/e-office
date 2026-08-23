"""RBAC-protected team endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.teams.models import TeamMemberRole
from meetinghq_api.modules.teams.schemas import (
    ChannelCreate,
    ChannelPreferenceUpdate,
    ChannelResponse,
    ChannelUpdate,
    TeamBulkMemberAction,
    TeamBulkResult,
    TeamCreate,
    TeamDocumentInput,
    TeamDocumentResponse,
    TeamIntegrationInput,
    TeamIntegrationResponse,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberRoleUpdate,
    TeamOverview,
    TeamResponse,
    TeamUpdate,
    TransferOwnershipRequest,
)
from meetinghq_api.modules.teams.service import TeamService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/teams", tags=["teams"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
    workspace_id: uuid.UUID | None = None,
    search: Annotated[str | None, Query(max_length=160)] = None,
    archived: bool | None = None,
    visibility: Annotated[str | None, Query(pattern=r"^(public|private)$")] = None,
) -> list[TeamResponse]:
    return [
        TeamResponse.model_validate(item)
        for item in await TeamService(session).list_teams(
            user.organization_id,
            workspace_id=workspace_id,
            search=search,
            archived=archived,
            visibility=visibility,
        )
    ]


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamResponse:
    return TeamResponse.model_validate(
        await TeamService(session).create(user.organization_id, body, user.id)
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> TeamResponse:
    return TeamResponse.model_validate(
        await TeamService(session).get(user.organization_id, team_id)
    )


@router.get("/{team_id}/overview", response_model=TeamOverview)
async def team_overview(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> TeamOverview:
    return await TeamService(session).overview(user.organization_id, team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamResponse:
    return TeamResponse.model_validate(
        await TeamService(session).update(user.organization_id, team_id, body, user.id)
    )


@router.post("/{team_id}/archive", response_model=TeamResponse)
async def archive_team(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamResponse:
    return TeamResponse.model_validate(
        await TeamService(session).lifecycle(user.organization_id, team_id, True, user.id)
    )


@router.post("/{team_id}/restore", response_model=TeamResponse)
async def restore_team(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamResponse:
    return TeamResponse.model_validate(
        await TeamService(session).lifecycle(user.organization_id, team_id, False, user.id)
    )


@router.get("/{team_id}/channels", response_model=list[ChannelResponse])
async def team_channels(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_READ)],
    search: Annotated[str | None, Query(max_length=160)] = None,
    archived: bool | None = None,
    channel_kind: Annotated[str | None, Query(max_length=24)] = None,
) -> list[ChannelResponse]:
    return await TeamService(session).channels(
        user.organization_id,
        team_id,
        user.id,
        search=search,
        archived=archived,
        channel_kind=channel_kind,
    )


@router.post("/{team_id}/channels", response_model=ChannelResponse, status_code=201)
async def create_team_channel(
    team_id: uuid.UUID,
    body: ChannelCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_MANAGE)],
) -> ChannelResponse:
    channel = await TeamService(session).create_channel(
        user.organization_id, team_id, body, user.id
    )
    rows = await TeamService(session).channels(user.organization_id, team_id, user.id)
    return next(item for item in rows if item.id == channel.id)


@router.patch("/{team_id}/channels/{channel_id}", response_model=ChannelResponse)
async def update_team_channel(
    team_id: uuid.UUID,
    channel_id: uuid.UUID,
    body: ChannelUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_MANAGE)],
) -> ChannelResponse:
    await TeamService(session).update_channel(
        user.organization_id, team_id, channel_id, body, user.id
    )
    rows = await TeamService(session).channels(user.organization_id, team_id, user.id)
    return next(item for item in rows if item.id == channel_id)


@router.post("/{team_id}/channels/{channel_id}/archive", response_model=OperationResponse)
async def archive_team_channel(
    team_id: uuid.UUID,
    channel_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_MANAGE)],
) -> OperationResponse:
    await TeamService(session).channel_lifecycle(
        user.organization_id, team_id, channel_id, True, user.id
    )
    return OperationResponse(message="Channel archived")


@router.post("/{team_id}/channels/{channel_id}/restore", response_model=OperationResponse)
async def restore_team_channel(
    team_id: uuid.UUID,
    channel_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_MANAGE)],
) -> OperationResponse:
    await TeamService(session).channel_lifecycle(
        user.organization_id, team_id, channel_id, False, user.id
    )
    return OperationResponse(message="Channel restored")


@router.put(
    "/{team_id}/channels/{channel_id}/preference",
    response_model=OperationResponse,
)
async def update_channel_preference(
    team_id: uuid.UUID,
    channel_id: uuid.UUID,
    body: ChannelPreferenceUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.CHAT_READ)],
) -> OperationResponse:
    await TeamService(session).set_channel_preference(
        user.organization_id, team_id, channel_id, user.id, body
    )
    return OperationResponse(message="Channel preference updated")


@router.get("/{team_id}/documents", response_model=list[TeamDocumentResponse])
async def team_documents(
    team_id: uuid.UUID,
    document_type: Annotated[str, Query(pattern=r"^(wiki|note)$")],
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> list[TeamDocumentResponse]:
    return [
        TeamDocumentResponse.model_validate(item)
        for item in await TeamService(session).documents(
            user.organization_id, team_id, document_type
        )
    ]


@router.post(
    "/{team_id}/documents",
    response_model=TeamDocumentResponse,
    status_code=201,
)
async def create_team_document(
    team_id: uuid.UUID,
    body: TeamDocumentInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamDocumentResponse:
    return TeamDocumentResponse.model_validate(
        await TeamService(session).create_document(user.organization_id, team_id, body, user.id)
    )


@router.get(
    "/{team_id}/integrations",
    response_model=list[TeamIntegrationResponse],
)
async def team_integrations(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> list[TeamIntegrationResponse]:
    return [
        TeamIntegrationResponse.model_validate(item)
        for item in await TeamService(session).integrations(user.organization_id, team_id)
    ]


@router.put("/{team_id}/integrations", response_model=TeamIntegrationResponse)
async def update_team_integration(
    team_id: uuid.UUID,
    body: TeamIntegrationInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamIntegrationResponse:
    return TeamIntegrationResponse.model_validate(
        await TeamService(session).upsert_integration(user.organization_id, team_id, body, user.id)
    )


@router.post("/{team_id}/members/bulk", response_model=TeamBulkResult)
async def bulk_team_members(
    team_id: uuid.UUID,
    body: TeamBulkMemberAction,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> TeamBulkResult:
    return await TeamService(session).bulk_members(
        user.organization_id, team_id, body.user_ids, body.action
    )


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
async def team_members(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> list[TeamMemberResponse]:
    return [
        TeamMemberResponse(
            id=member.id,
            user_id=member.user_id,
            email=member_user.email,
            display_name=member_user.display_name,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, member_user in await TeamService(session).members(user.organization_id, team_id)
    ]


@router.post("/{team_id}/members", response_model=OperationResponse, status_code=201)
async def add_team_member(
    team_id: uuid.UUID,
    body: TeamMemberCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> OperationResponse:
    await TeamService(session).add_member(
        user.organization_id, team_id, body.user_id, body.role, user.id
    )
    return OperationResponse(message="Member added")


@router.patch("/{team_id}/members/{user_id}", response_model=OperationResponse)
async def update_member_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    body: TeamMemberRoleUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> OperationResponse:
    await TeamService(session).set_role(user.organization_id, team_id, user_id, body.role)
    return OperationResponse(message="Member role updated")


@router.delete("/{team_id}/members/{user_id}", response_model=OperationResponse)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> OperationResponse:
    await TeamService(session).remove_member(user.organization_id, team_id, user_id)
    return OperationResponse(message="Member removed")


@router.post("/{team_id}/transfer-ownership", response_model=OperationResponse)
async def transfer_team(
    team_id: uuid.UUID,
    body: TransferOwnershipRequest,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_WRITE)],
) -> OperationResponse:
    await TeamService(session).transfer(user.organization_id, team_id, body.user_id)
    return OperationResponse(message="Ownership transferred")


@router.post("/{team_id}/join", response_model=OperationResponse)
async def join_team(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> OperationResponse:
    await TeamService(session).add_member(
        user.organization_id, team_id, user.id, TeamMemberRole.MEMBER, user.id
    )
    return OperationResponse(message="Joined team")


@router.post("/{team_id}/leave", response_model=OperationResponse)
async def leave_team(
    team_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.TEAMS_READ)],
) -> OperationResponse:
    await TeamService(session).leave(user.organization_id, team_id, user.id)
    return OperationResponse(message="Left team")
