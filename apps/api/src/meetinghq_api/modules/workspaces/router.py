"""RBAC-protected workspace endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.schemas import (
    WorkspaceBulkAction,
    WorkspaceBulkResult,
    WorkspaceCreate,
    WorkspaceIntegrationInput,
    WorkspaceIntegrationResponse,
    WorkspaceMemberInput,
    WorkspaceMemberResponse,
    WorkspaceOverview,
    WorkspaceResponse,
    WorkspaceTemplateInput,
    WorkspaceTemplateResponse,
    WorkspaceUpdate,
)
from meetinghq_api.modules.workspaces.service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
    search: Annotated[str | None, Query(max_length=160)] = None,
    archived: bool | None = None,
    classification: Annotated[str | None, Query(max_length=40)] = None,
) -> list[WorkspaceResponse]:
    return [
        WorkspaceResponse.model_validate(item)
        for item in await WorkspaceService(session).list_workspaces(
            user.organization_id,
            search=search,
            archived=archived,
            classification=classification,
        )
    ]


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        await WorkspaceService(session).create(user.organization_id, body, user.id)
    )


@router.post("/bulk/lifecycle", response_model=WorkspaceBulkResult)
async def bulk_workspace_lifecycle(
    body: WorkspaceBulkAction,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceBulkResult:
    return await WorkspaceService(session).bulk_lifecycle(
        user.organization_id, body.workspace_ids, body.action, user.id
    )


@router.get("/templates/catalog", response_model=list[WorkspaceTemplateResponse])
async def list_workspace_templates(
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
) -> list[WorkspaceTemplateResponse]:
    return [
        WorkspaceTemplateResponse.model_validate(item)
        for item in await WorkspaceService(session).templates(user.organization_id)
    ]


@router.post(
    "/templates/catalog",
    response_model=WorkspaceTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_template(
    body: WorkspaceTemplateInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceTemplateResponse:
    return WorkspaceTemplateResponse.model_validate(
        await WorkspaceService(session).create_template(user.organization_id, body, user.id)
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        await WorkspaceService(session).get(user.organization_id, workspace_id)
    )


@router.get("/{workspace_id}/overview", response_model=WorkspaceOverview)
async def workspace_overview(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
) -> WorkspaceOverview:
    return await WorkspaceService(session).overview(user.organization_id, workspace_id)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def workspace_members(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
) -> list[WorkspaceMemberResponse]:
    return await WorkspaceService(session).members(user.organization_id, workspace_id)


@router.put("/{workspace_id}/members", response_model=WorkspaceMemberResponse)
async def assign_workspace_member(
    workspace_id: uuid.UUID,
    body: WorkspaceMemberInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceMemberResponse:
    return await WorkspaceService(session).add_member(
        user.organization_id, workspace_id, body, user.id
    )


@router.delete(
    "/{workspace_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> Response:
    await WorkspaceService(session).remove_member(
        user.organization_id, workspace_id, member_user_id, user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workspace_id}/integrations",
    response_model=list[WorkspaceIntegrationResponse],
)
async def list_workspace_integrations(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_READ)],
) -> list[WorkspaceIntegrationResponse]:
    return [
        WorkspaceIntegrationResponse.model_validate(item)
        for item in await WorkspaceService(session).integrations(user.organization_id, workspace_id)
    ]


@router.put(
    "/{workspace_id}/integrations",
    response_model=WorkspaceIntegrationResponse,
)
async def update_workspace_integration(
    workspace_id: uuid.UUID,
    body: WorkspaceIntegrationInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceIntegrationResponse:
    return WorkspaceIntegrationResponse.model_validate(
        await WorkspaceService(session).upsert_integration(
            user.organization_id, workspace_id, body, user.id
        )
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        await WorkspaceService(session).update(user.organization_id, workspace_id, body, user.id)
    )


@router.post("/{workspace_id}/archive", response_model=WorkspaceResponse)
async def archive_workspace(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        await WorkspaceService(session).archive(user.organization_id, workspace_id, True, user.id)
    )


@router.post("/{workspace_id}/restore", response_model=WorkspaceResponse)
async def restore_workspace(
    workspace_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.WORKSPACES_WRITE)],
) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(
        await WorkspaceService(session).archive(user.organization_id, workspace_id, False, user.id)
    )
