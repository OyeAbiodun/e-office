"""Idempotently seed a complete local MeetingHQ demonstration workspace."""

import asyncio
from datetime import UTC, date, datetime, time

from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.database import session_factory
from meetinghq_api.modules.auth.application.service import AuthService
from meetinghq_api.modules.auth.presentation.schemas import RegisterRequest
from meetinghq_api.modules.calendar.models import (
    AvailabilityRule,
    Calendar,
    CalendarEvent,
    CalendarType,
    Holiday,
    Resource,
)
from meetinghq_api.modules.calendar.schemas import CalendarCreate, HolidayCreate, ResourceCreate
from meetinghq_api.modules.calendar.service import (
    CalendarRulesService,
    CalendarService,
    ResourceService,
)
from meetinghq_api.modules.teams.models import Team  # noqa: F401
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import Workspace

DEMO_EMAIL = "demo@meetinghq.example.com"
DEMO_PASSWORD = "MeetingHQ-Demo-2026!"


async def seed() -> None:
    settings = get_settings()
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            registered = await AuthService(session, settings).register(
                RegisterRequest(
                    organization_name="MeetingHQ Demo",
                    organization_slug="meetinghq-demo",
                    workspace_name="Demo Workspace",
                    email=DEMO_EMAIL,
                    username="demo.admin",
                    first_name="Demo",
                    last_name="Administrator",
                    password=DEMO_PASSWORD,
                ),
                ip_address="127.0.0.1",
                user_agent="development-seed",
            )
            user = await session.get(User, registered.user.id)
        if user is None:
            raise RuntimeError("Development user seed failed")
        workspace = await session.scalar(
            select(Workspace).where(Workspace.organization_id == user.organization_id)
        )
        if workspace is None:
            raise RuntimeError("Development workspace seed failed")
        calendar = await session.scalar(
            select(Calendar).where(
                Calendar.organization_id == user.organization_id,
                Calendar.name == "Demo Schedule",
            )
        )
        if calendar is None:
            calendar = await CalendarService(session).create(
                user.organization_id,
                CalendarCreate(
                    workspace_id=workspace.id,
                    owner_id=user.id,
                    name="Demo Schedule",
                    type=CalendarType.PERSONAL,
                    timezone="America/Chicago",
                    is_default=True,
                ),
                user.id,
            )
            session.add_all(
                [
                    AvailabilityRule(
                        calendar_id=calendar.id,
                        weekday=weekday,
                        start_time=time(8),
                        end_time=time(18),
                    )
                    for weekday in range(5)
                ]
            )
            session.add(
                CalendarEvent(
                    calendar_id=calendar.id,
                    title="Weekly planning",
                    start_datetime=datetime(2026, 8, 3, 14, tzinfo=UTC),
                    end_datetime=datetime(2026, 8, 3, 15, tzinfo=UTC),
                    timezone="America/Chicago",
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
        if not await session.scalar(
            select(Holiday.id).where(
                Holiday.organization_id == user.organization_id,
                Holiday.name == "Labor Day",
            )
        ):
            await CalendarRulesService(session).create_holiday(
                user.organization_id,
                HolidayCreate(name="Labor Day", date=date(2026, 9, 7)),
                user.id,
            )
        if not await session.scalar(
            select(Resource.id).where(
                Resource.organization_id == user.organization_id,
                Resource.name == "Boardroom A",
            )
        ):
            await ResourceService(session).create(
                user.organization_id,
                ResourceCreate(
                    workspace_id=workspace.id,
                    name="Boardroom A",
                    category="Meeting Room",
                    capacity=12,
                    location="Floor 2",
                    timezone="America/Chicago",
                ),
                user.id,
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
