"""Super Admin Audit Center API."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.audit.schemas import AuditFilters, AuditPageResponse
from meetinghq_api.modules.audit.service import AuditService
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/audit", tags=["audit-center"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
SuperAdmin = Annotated[User, require_permission(Permissions.ADMIN_MANAGE)]


def filters(
    search: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=80),
    action: str | None = Query(default=None, max_length=120),
    user_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> AuditFilters:
    return AuditFilters(
        search=search,
        category=category,
        action=action,
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
    )


AuditFilterDependency = Annotated[AuditFilters, Depends(filters)]


@router.get("", response_model=AuditPageResponse)
async def list_audit_records(
    session: Session,
    user: SuperAdmin,
    audit_filters: AuditFilterDependency,
    cursor: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditPageResponse:
    return await AuditService(session).list_records(
        user.organization_id,
        audit_filters,
        cursor=cursor,
        offset=offset,
        limit=limit,
    )


@router.get("/export")
async def export_audit_records(
    session: Session,
    user: SuperAdmin,
    audit_filters: AuditFilterDependency,
) -> Response:
    body = await AuditService(session).export_csv(user.organization_id, audit_filters)
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="meetinghq-audit.csv"'},
    )
