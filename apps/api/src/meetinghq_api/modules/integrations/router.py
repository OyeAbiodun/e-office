"""Integration Center endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.integrations.schemas import (
    IntegrationAuditResponse,
    IntegrationConfigurationUpdate,
    IntegrationOperationResponse,
    IntegrationResponse,
    IntegrationTestResponse,
)
from meetinghq_api.modules.integrations.service import IntegrationService
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/integrations", tags=["integration-center"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
SuperAdmin = Annotated[User, require_permission(Permissions.ADMIN_MANAGE)]


@router.get("", response_model=list[IntegrationResponse])
async def integrations(session: Session, user: SuperAdmin) -> list[IntegrationResponse]:
    return await IntegrationService(session).list(user.organization_id)


@router.put("/{key}", response_model=IntegrationResponse)
async def configure_integration(
    key: str,
    body: IntegrationConfigurationUpdate,
    session: Session,
    user: SuperAdmin,
) -> IntegrationResponse:
    return await IntegrationService(session).configure(user.organization_id, key, body.values, user)


@router.delete("/{key}", response_model=IntegrationOperationResponse)
async def disconnect_integration(
    key: str, session: Session, user: SuperAdmin
) -> IntegrationOperationResponse:
    await IntegrationService(session).disconnect(user.organization_id, key, user)
    return IntegrationOperationResponse(
        key=key, configured=False, message="Integration disconnected"
    )


@router.post("/{key}/test", response_model=IntegrationTestResponse)
async def test_integration(key: str, session: Session, user: SuperAdmin) -> IntegrationTestResponse:
    return await IntegrationService(session).test_connection(user.organization_id, key, user)


@router.post("/{key}/synchronize", response_model=IntegrationOperationResponse)
async def synchronize_integration(
    key: str, session: Session, user: SuperAdmin
) -> IntegrationOperationResponse:
    await IntegrationService(session).synchronize(user.organization_id, key, user)
    return IntegrationOperationResponse(
        key=key,
        configured=True,
        message="Provider synchronization queued",
    )


@router.get("/{key}/audit", response_model=list[IntegrationAuditResponse])
async def integration_audit(
    key: str, session: Session, user: SuperAdmin
) -> list[IntegrationAuditResponse]:
    rows = await IntegrationService(session).audit_history(user.organization_id, key)
    return [
        IntegrationAuditResponse(
            action=row.action,
            status=str(row.audit_metadata.get("status", "recorded")),
            created_at=row.created_at,
            actor_id=str(row.user_id) if row.user_id else None,
        )
        for row in rows
    ]
