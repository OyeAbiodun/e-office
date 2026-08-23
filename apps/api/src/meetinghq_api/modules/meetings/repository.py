"""Tenant-scoped meeting persistence."""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.meetings.models import Meeting
from meetinghq_api.shared.repository import SqlAlchemyRepository


class MeetingRepository(SqlAlchemyRepository[Meeting]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Meeting)

    async def get(self, organization_id: uuid.UUID, meeting_id: uuid.UUID) -> Meeting | None:
        return cast(
            Meeting | None,
            await self.session.scalar(
                select(Meeting).where(
                    Meeting.id == meeting_id, Meeting.organization_id == organization_id
                )
            ),
        )

    async def find(
        self,
        organization_id: uuid.UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
    ) -> list[Meeting]:
        query = select(Meeting).where(Meeting.organization_id == organization_id)
        if start:
            query = query.where(Meeting.end_datetime >= start)
        if end:
            query = query.where(Meeting.start_datetime <= end)
        if status:
            query = query.where(Meeting.status == status)
        return list((await self.session.scalars(query.order_by(Meeting.start_datetime))).all())

    async def involved(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> list[Meeting]:
        from meetinghq_api.modules.meetings.models import MeetingAttendee

        return list(
            (
                await self.session.scalars(
                    select(Meeting)
                    .outerjoin(MeetingAttendee, MeetingAttendee.meeting_id == Meeting.id)
                    .where(
                        Meeting.organization_id == organization_id,
                        or_(Meeting.organizer_id == user_id, MeetingAttendee.user_id == user_id),
                    )
                    .distinct()
                    .order_by(Meeting.start_datetime)
                )
            ).all()
        )
