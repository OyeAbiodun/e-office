"""RBAC-protected organization endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.organizations.models import OrganizationUnitType
from meetinghq_api.modules.organizations.schemas import (
    DepartmentDetailResponse,
    DepartmentDirectoryResponse,
    OrganizationCreate,
    OrganizationOverview,
    OrganizationPolicyUpdate,
    OrganizationResponse,
    OrganizationUnitInput,
    OrganizationUnitResponse,
    OrganizationUpdate,
)
from meetinghq_api.modules.organizations.service import OrganizationService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/organizations", tags=["organizations"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/current", response_model=OrganizationResponse)
async def current_organization(
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(
        await OrganizationService(session).get(user.organization_id)
    )


@router.get("/current/overview", response_model=OrganizationOverview)
async def organization_overview(
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
) -> OrganizationOverview:
    return await OrganizationService(session).overview(user.organization_id)


@router.get("/current/units", response_model=list[OrganizationUnitResponse])
async def organization_units(
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
    unit_type: OrganizationUnitType | None = None,
) -> list[OrganizationUnitResponse]:
    return [
        OrganizationUnitResponse.model_validate(unit)
        for unit in await OrganizationService(session).units(user.organization_id, unit_type)
    ]


@router.get("/current/departments", response_model=DepartmentDirectoryResponse)
async def departments(
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
    search: str | None = Query(default=None, max_length=160),
    status: str | None = Query(default=None, pattern=r"^(active|inactive)$"),
    sort: str = Query(default="name", pattern=r"^(name|created_at)$"),
    direction: str = Query(default="asc", pattern=r"^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> DepartmentDirectoryResponse:
    rows, total = await OrganizationService(session).departments(
        user.organization_id,
        search=search,
        status=status,
        sort=sort,
        direction=direction,
        page=page,
        page_size=page_size,
    )
    return DepartmentDirectoryResponse(
        items=[OrganizationUnitResponse.model_validate(unit) for unit in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/current/units", response_model=OrganizationUnitResponse, status_code=201)
async def create_organization_unit(
    body: OrganizationUnitInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OrganizationUnitResponse:
    return OrganizationUnitResponse.model_validate(
        await OrganizationService(session).create_unit(user.organization_id, body, user.id)
    )


@router.put("/current/units/{unit_id}", response_model=OrganizationUnitResponse)
async def update_organization_unit(
    unit_id: uuid.UUID,
    body: OrganizationUnitInput,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OrganizationUnitResponse:
    return OrganizationUnitResponse.model_validate(
        await OrganizationService(session).update_unit(user.organization_id, unit_id, body, user.id)
    )


@router.get("/current/departments/{unit_id}", response_model=DepartmentDetailResponse)
async def department_detail(
    unit_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
) -> DepartmentDetailResponse:
    return await OrganizationService(session).department_detail(user.organization_id, unit_id)


@router.delete("/current/units/{unit_id}", response_model=OperationResponse)
async def delete_organization_unit(
    unit_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OperationResponse:
    await OrganizationService(session).delete_unit(user.organization_id, unit_id, user.id)
    return OperationResponse(message="Organization unit archived")


@router.get("/current/policies")
async def organization_policies(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_READ)],
) -> dict[str, dict[str, object]]:
    return await OrganizationService(session).policies(user.organization_id, settings)


@router.put("/current/policies/{category}")
async def update_organization_policy(
    category: str,
    body: OrganizationPolicyUpdate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> dict[str, object]:
    return await OrganizationService(session).set_policy(
        user.organization_id, settings, category, body.values, user.id
    )


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    body: OrganizationCreate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(
        await OrganizationService(session).create(body, user.id)
    )


@router.patch("/current", response_model=OrganizationResponse)
async def update_organization(
    body: OrganizationUpdate,
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(
        await OrganizationService(session).update(user.organization_id, body, user.id)
    )


@router.delete("/current", response_model=OperationResponse)
async def delete_organization(
    session: Session,
    user: Annotated[User, require_permission(Permissions.ORGANIZATIONS_WRITE)],
) -> OperationResponse:
    await OrganizationService(session).soft_delete(user.organization_id, user.id)
    return OperationResponse(message="Organization deleted")
