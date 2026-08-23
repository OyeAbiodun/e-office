"""System health administration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.system_health.schemas import (
    HealthHistoryPoint,
    SystemHealthResponse,
)
from meetinghq_api.modules.system_health.service import SystemHealthService
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/system-health", tags=["system-health"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
SuperAdmin = Annotated[User, require_permission(Permissions.ADMIN_MANAGE)]


@router.get("", response_model=SystemHealthResponse)
async def system_health(
    session: Session, settings: AppSettings, user: SuperAdmin
) -> SystemHealthResponse:
    return await SystemHealthService(session, settings).snapshot(user.organization_id)


@router.get("/history", response_model=list[HealthHistoryPoint])
async def system_health_history(
    session: Session,
    settings: AppSettings,
    user: SuperAdmin,
    limit: int = Query(default=96, ge=1, le=500),
) -> list[HealthHistoryPoint]:
    return await SystemHealthService(session, settings).history(user.organization_id, limit)
