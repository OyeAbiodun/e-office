"""Calendar persistence adapters."""

# ruff: noqa: E501

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.calendar.models import (
    BusyBlock,
    Calendar,
    CalendarEvent,
    EventStatus,
    Resource,
    ResourceReservation,
)
from meetinghq_api.shared.repository import SqlAlchemyRepository


class CalendarRepository(SqlAlchemyRepository[Calendar]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Calendar)

    async def get(self, organization_id: uuid.UUID, calendar_id: uuid.UUID) -> Calendar | None:
        return cast(
            Calendar | None,
            await self.scalar(
                select(Calendar).where(
                    Calendar.id == calendar_id,
                    Calendar.organization_id == organization_id,
                    Calendar.deleted_at.is_(None),
                )
            ),
        )

    async def list(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[Calendar]:
        return list(
            await self.all(
                select(Calendar)
                .where(
                    Calendar.organization_id == organization_id,
                    Calendar.deleted_at.is_(None),
                    or_(
                        Calendar.owner_id == user_id,
                        Calendar.type != "personal",
                    ),
                )
                .order_by(Calendar.is_default.desc(), Calendar.name)
            )
        )


class SchedulingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_models(self, statement: Select[Any]) -> list[Any]:
        return list((await self.session.scalars(statement)).all())

    async def busy_ranges(
        self,
        calendar_ids: list[uuid.UUID],
        resource_ids: list[uuid.UUID],
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        event_rows = await self.session.execute(
            select(CalendarEvent.start_datetime, CalendarEvent.end_datetime).where(
                CalendarEvent.calendar_id.in_(calendar_ids),
                CalendarEvent.status != EventStatus.CANCELLED,
                CalendarEvent.deleted_at.is_(None),
                CalendarEvent.start_datetime < end,
                CalendarEvent.end_datetime > start,
            )
        )
        block_rows = await self.session.execute(
            select(BusyBlock.start_datetime, BusyBlock.end_datetime).where(
                BusyBlock.calendar_id.in_(calendar_ids),
                BusyBlock.start_datetime < end,
                BusyBlock.end_datetime > start,
            )
        )
        reservation_rows = await self.session.execute(
            select(
                ResourceReservation.start_datetime,
                ResourceReservation.end_datetime,
            ).where(
                ResourceReservation.resource_id.in_(resource_ids),
                ResourceReservation.cancelled_at.is_(None),
                ResourceReservation.start_datetime < end,
                ResourceReservation.end_datetime > start,
            )
        )
        rows = [
            *event_rows.tuples().all(),
            *block_rows.tuples().all(),
            *reservation_rows.tuples().all(),
        ]
        return [
            (
                start.replace(tzinfo=UTC) if start.tzinfo is None else start,
                finish.replace(tzinfo=UTC) if finish.tzinfo is None else finish,
            )
            for start, finish in rows
        ]

    async def calendar_owned(self, organization_id: uuid.UUID, calendar_id: uuid.UUID) -> bool:
        return (
            await self.session.scalar(
                select(Calendar.id).where(
                    Calendar.id == calendar_id,
                    Calendar.organization_id == organization_id,
                    Calendar.deleted_at.is_(None),
                )
            )
            is not None
        )

    async def resource_owned(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        return (
            await self.session.scalar(
                select(Resource.id).where(
                    Resource.id == resource_id,
                    Resource.organization_id == organization_id,
                    Resource.deleted_at.is_(None),
                )
            )
            is not None
        )
