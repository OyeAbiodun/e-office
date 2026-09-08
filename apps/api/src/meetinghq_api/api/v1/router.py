"""Version 1 route composition."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from meetinghq_api.dependencies import check_database, check_redis
from meetinghq_api.modules.audit.router import router as audit_router
from meetinghq_api.modules.auth.presentation.router import router as auth_router
from meetinghq_api.modules.calendar.router import router as calendar_router
from meetinghq_api.modules.chat.router import router as chat_router
from meetinghq_api.modules.configuration.router import router as configuration_router
from meetinghq_api.modules.dashboard.router import router as dashboard_router
from meetinghq_api.modules.finance.router import router as finance_router
from meetinghq_api.modules.help_center.router import router as help_router
from meetinghq_api.modules.integrations.router import router as integrations_router
from meetinghq_api.modules.invitations.router import router as invitations_router
from meetinghq_api.modules.leave.router import router as leave_router
from meetinghq_api.modules.mail.router import router as mail_router
from meetinghq_api.modules.meetings.router import router as meetings_router
from meetinghq_api.modules.notifications.router import router as notifications_router
from meetinghq_api.modules.organizations.router import router as organizations_router
from meetinghq_api.modules.search.router import router as search_router
from meetinghq_api.modules.storage.router import router as storage_router
from meetinghq_api.modules.system_health.router import router as system_health_router
from meetinghq_api.modules.tasks.router import router as tasks_router
from meetinghq_api.modules.teams.router import router as teams_router
from meetinghq_api.modules.users.router import router as users_router
from meetinghq_api.modules.workspaces.router import router as workspaces_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(audit_router)
router.include_router(calendar_router)
router.include_router(chat_router)
router.include_router(configuration_router)
router.include_router(organizations_router)
router.include_router(workspaces_router)
router.include_router(teams_router)
router.include_router(users_router)
router.include_router(invitations_router)
router.include_router(integrations_router)
router.include_router(leave_router)
router.include_router(help_router)
router.include_router(mail_router)
router.include_router(meetings_router)
router.include_router(notifications_router)
router.include_router(tasks_router)
router.include_router(finance_router)
router.include_router(dashboard_router)
router.include_router(search_router)
router.include_router(storage_router)
router.include_router(system_health_router)


class HealthResponse(BaseModel):
    """Health endpoint response contract."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Readiness endpoint response contract."""

    status: Literal["ready"]
    database: Literal["ok"]
    redis: Literal["ok"]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Check API liveness",
)
async def health() -> HealthResponse:
    """Return success when the HTTP process is alive."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    tags=["system"],
    summary="Check API readiness",
)
async def readiness(
    _database: Annotated[None, Depends(check_database)],
    _redis: Annotated[None, Depends(check_redis)],
) -> ReadinessResponse:
    """Return success when required infrastructure is reachable."""
    return ReadinessResponse(status="ready", database="ok", redis="ok")
