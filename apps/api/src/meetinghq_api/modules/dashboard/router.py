"""Widget-based organization dashboard endpoint."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.calendar.models import (
    Calendar,
    CalendarEvent,
    Holiday,
    Resource,
    ResourceStatus,
)
from meetinghq_api.modules.dashboard.schemas import (
    ActivityItem,
    DashboardResponse,
    MetricWidget,
)
from meetinghq_api.modules.invitations.models import Invitation, InvitationStatus
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import Workspace

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("", response_model=DashboardResponse)
async def dashboard(
    session: Session,
    user: Annotated[User, require_permission("dashboard.view")],
) -> DashboardResponse:
    """Compose independently renderable tenant widgets."""
    organization = await session.get(Organization, user.organization_id)
    workspace_count = await session.scalar(
        select(func.count(Workspace.id)).where(
            Workspace.organization_id == user.organization_id,
            Workspace.archived_at.is_(None),
        )
    )
    team_count = await session.scalar(
        select(func.count(Team.id)).where(Team.organization_id == user.organization_id)
    )
    member_count = await session.scalar(
        select(func.count(User.id)).where(
            User.organization_id == user.organization_id, User.removed_at.is_(None)
        )
    )
    invitation_count = await session.scalar(
        select(func.count(Invitation.id)).where(
            Invitation.organization_id == user.organization_id,
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    now = datetime.now(UTC)
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)
    today_count = await session.scalar(
        select(func.count(CalendarEvent.id))
        .join(Calendar, Calendar.id == CalendarEvent.calendar_id)
        .where(
            Calendar.organization_id == user.organization_id,
            CalendarEvent.start_datetime >= now,
            CalendarEvent.start_datetime < tomorrow,
            CalendarEvent.deleted_at.is_(None),
        )
    )
    upcoming_count = await session.scalar(
        select(func.count(CalendarEvent.id))
        .join(Calendar, Calendar.id == CalendarEvent.calendar_id)
        .where(
            Calendar.organization_id == user.organization_id,
            CalendarEvent.start_datetime >= now,
            CalendarEvent.start_datetime < next_week,
            CalendarEvent.deleted_at.is_(None),
        )
    )
    resource_count = await session.scalar(
        select(func.count(Resource.id)).where(
            Resource.organization_id == user.organization_id,
            Resource.status == ResourceStatus.AVAILABLE,
            Resource.deleted_at.is_(None),
        )
    )
    holiday_count = await session.scalar(
        select(func.count(Holiday.id)).where(Holiday.organization_id == user.organization_id)
    )
    events = (
        await session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.organization_id == user.organization_id)
            .order_by(ActivityEvent.occurred_at.desc())
            .limit(10)
        )
    ).all()
    return DashboardResponse(
        organization_name=organization.name if organization else "Organization",
        widgets=[
            MetricWidget(id="workspaces", label="Workspaces", value=workspace_count or 0),
            MetricWidget(id="teams", label="Teams", value=team_count or 0),
            MetricWidget(id="members", label="Members", value=member_count or 0),
            MetricWidget(
                id="invitations",
                label="Pending invitations",
                value=invitation_count or 0,
            ),
            MetricWidget(id="today_schedule", label="Today's schedule", value=today_count or 0),
            MetricWidget(id="upcoming_events", label="Upcoming events", value=upcoming_count or 0),
            MetricWidget(id="availability", label="Availability", value=100),
            MetricWidget(
                id="resource_status", label="Available resources", value=resource_count or 0
            ),
            MetricWidget(id="holiday_summary", label="Holidays", value=holiday_count or 0),
            MetricWidget(id="quick_schedule", label="Quick schedule", value=1),
        ],
        recent_activity=[
            ActivityItem(
                id=str(event.id),
                event_type=event.event_type,
                subject_type=event.subject_type,
                occurred_at=event.occurred_at,
                payload=event.payload,
            )
            for event in events
        ],
        quick_actions=["Quick schedule", "Create workspace", "Create team", "Invite member"],
    )
