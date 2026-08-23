"""Calendar platform application services."""

# ruff: noqa: E501

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.calendar.models import (
    AvailabilityRule,
    BusyBlock,
    Calendar,
    CalendarEvent,
    CalendarShare,
    CalendarType,
    EventCategory,
    EventStatus,
    Holiday,
    RecurrenceRule,
    Resource,
    ResourceReservation,
)
from meetinghq_api.modules.calendar.repository import CalendarRepository, SchedulingRepository
from meetinghq_api.modules.calendar.scheduling import (
    SchedulingEngine,
    SchedulingPolicy,
    TimeRange,
    ValidationResult,
)
from meetinghq_api.modules.calendar.schemas import (
    AvailabilityCreate,
    BusyBlockCreate,
    CalendarCreate,
    CalendarUpdate,
    EventCategoryCreate,
    EventCreate,
    EventUpdate,
    HolidayCreate,
    RecurrenceExceptionCreate,
    RecurrenceRuleInput,
    ReservationCreate,
    ResourceCreate,
    ScheduleValidationRequest,
    SlotSuggestionRequest,
)
from meetinghq_api.modules.calendar.timezone import TimezoneService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.events import DomainEvent, DomainEventPublisher
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError


def append_audit(
    session: AsyncSession,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    resource: str,
    resource_id: uuid.UUID,
) -> None:
    session.add(
        AuditLog(
            organization_id=organization_id,
            user_id=actor_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            audit_metadata={},
        )
    )


class CalendarService:
    """Calendar and event use cases with tenant isolation and auditability."""

    def __init__(self, session: AsyncSession, events: DomainEventPublisher | None = None) -> None:
        self.session = session
        self.repository = CalendarRepository(session)
        self.events = events or TransactionalDomainEventPublisher(session)
        self.timezones = TimezoneService()

    async def list_calendars(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Calendar]:
        return await self.repository.list(organization_id, user_id)

    async def get(self, organization_id: uuid.UUID, calendar_id: uuid.UUID) -> Calendar:
        calendar = await self.repository.get(organization_id, calendar_id)
        if calendar is None:
            raise NotFoundError("Calendar not found")
        return calendar

    async def create(
        self, organization_id: uuid.UUID, body: CalendarCreate, actor_id: uuid.UUID
    ) -> Calendar:
        self.timezones.validate(body.timezone)
        if body.type.value == "personal" and body.owner_id not in {None, actor_id}:
            raise ValidationError("Personal calendars must belong to the current user")
        calendar = Calendar(
            organization_id=organization_id,
            **body.model_dump(exclude={"owner_id"}),
            owner_id=body.owner_id or (actor_id if body.type.value == "personal" else None),
        )
        await self.repository.add(calendar)
        await self._record("CalendarCreated", calendar, actor_id)
        return calendar

    async def update(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        body: CalendarUpdate,
        actor_id: uuid.UUID,
    ) -> Calendar:
        calendar = await self.get(organization_id, calendar_id)
        values = body.model_dump(exclude_unset=True)
        if values.get("timezone"):
            self.timezones.validate(str(values["timezone"]))
        for field, value in values.items():
            setattr(calendar, field, value)
        await self._record("CalendarUpdated", calendar, actor_id)
        return calendar

    async def delete(
        self, organization_id: uuid.UUID, calendar_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        calendar = await self.get(organization_id, calendar_id)
        calendar.soft_delete(actor_id)
        await self._record("CalendarDeleted", calendar, actor_id)

    async def list_events(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        start: datetime | None,
        end: datetime | None,
    ) -> list[CalendarEvent]:
        await self.get(organization_id, calendar_id)
        statement = select(CalendarEvent).where(
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.deleted_at.is_(None),
        )
        if start:
            statement = statement.where(CalendarEvent.end_datetime > start)
        if end:
            statement = statement.where(CalendarEvent.start_datetime < end)
        return list(
            (await self.session.scalars(statement.order_by(CalendarEvent.start_datetime))).all()
        )

    async def create_event(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        body: EventCreate,
        actor_id: uuid.UUID,
    ) -> CalendarEvent:
        calendar = await self.get(organization_id, calendar_id)
        if body.category_id is not None:
            await self._require_category(organization_id, body.category_id)
        start = self.timezones.to_utc(body.start_datetime, body.timezone)
        end = self.timezones.to_utc(body.end_datetime, body.timezone)
        validation = await SchedulingService(self.session).validate(
            organization_id,
            ScheduleValidationRequest(
                calendar_ids=[calendar_id],
                start_datetime=start,
                end_datetime=end,
                timezone="UTC",
            ),
        )
        if not validation.valid:
            raise ConflictError("; ".join(validation.reasons))
        event = CalendarEvent(
            calendar_id=calendar_id,
            created_by=actor_id,
            updated_by=actor_id,
            **body.model_dump(exclude={"start_datetime", "end_datetime", "recurrence"}),
            start_datetime=start,
            end_datetime=end,
        )
        if body.recurrence is not None:
            rule = RecurrenceRule(
                **body.recurrence.model_dump(),
                exception_dates=[],
            )
            self.session.add(rule)
            await self.session.flush()
            event.recurrence_rule_id = rule.id
        self.session.add(event)
        await self.session.flush()
        await self._record("CalendarEventCreated", calendar, actor_id, event.id)
        return event

    async def get_event(
        self, organization_id: uuid.UUID, event_id: uuid.UUID
    ) -> tuple[Calendar, CalendarEvent]:
        row = (
            await self.session.execute(
                select(Calendar, CalendarEvent)
                .join(CalendarEvent, CalendarEvent.calendar_id == Calendar.id)
                .where(
                    CalendarEvent.id == event_id,
                    CalendarEvent.deleted_at.is_(None),
                    Calendar.organization_id == organization_id,
                    Calendar.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Calendar event not found")
        return row[0], row[1]

    async def update_event(
        self,
        organization_id: uuid.UUID,
        event_id: uuid.UUID,
        body: EventUpdate,
        actor_id: uuid.UUID,
    ) -> CalendarEvent:
        calendar, event = await self.get_event(organization_id, event_id)
        values = body.model_dump(exclude_unset=True)
        if values.get("category_id") is not None:
            await self._require_category(organization_id, values["category_id"])
        timezone = str(values.get("timezone") or event.timezone)
        self.timezones.validate(timezone)
        start = values.pop("start_datetime", event.start_datetime)
        end = values.pop("end_datetime", event.end_datetime)
        start_utc = self.timezones.to_utc(start, timezone)
        end_utc = self.timezones.to_utc(end, timezone)
        if end_utc <= start_utc:
            raise ValidationError("end_datetime must be after start_datetime")
        conflict = await self.session.scalar(
            select(CalendarEvent.id).where(
                CalendarEvent.calendar_id == event.calendar_id,
                CalendarEvent.id != event.id,
                CalendarEvent.status != EventStatus.CANCELLED,
                CalendarEvent.deleted_at.is_(None),
                CalendarEvent.start_datetime < end_utc,
                CalendarEvent.end_datetime > start_utc,
            )
        )
        if conflict is not None:
            raise ConflictError("Calendar is unavailable during this time")
        for field, value in values.items():
            setattr(event, field, value)
        event.start_datetime = start_utc
        event.end_datetime = end_utc
        event.updated_by = actor_id
        await self._record("CalendarEventUpdated", calendar, actor_id, event.id)
        return event

    async def delete_event(
        self, organization_id: uuid.UUID, event_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        calendar, event = await self.get_event(organization_id, event_id)
        event.soft_delete(actor_id)
        await self._record("CalendarEventDeleted", calendar, actor_id, event.id)

    async def recurrence(
        self, organization_id: uuid.UUID, event_id: uuid.UUID
    ) -> RecurrenceRule | None:
        _, event = await self.get_event(organization_id, event_id)
        if event.recurrence_rule_id is None:
            return None
        return await self.session.get(RecurrenceRule, event.recurrence_rule_id)

    async def set_recurrence(
        self,
        organization_id: uuid.UUID,
        event_id: uuid.UUID,
        body: RecurrenceRuleInput,
        actor_id: uuid.UUID,
    ) -> RecurrenceRule:
        calendar, event = await self.get_event(organization_id, event_id)
        rule = await self.recurrence(organization_id, event_id)
        if rule is None:
            rule = RecurrenceRule(**body.model_dump(), exception_dates=[])
            self.session.add(rule)
            await self.session.flush()
            event.recurrence_rule_id = rule.id
        else:
            for field, value in body.model_dump().items():
                setattr(rule, field, value)
        event.updated_by = actor_id
        await self._record("CalendarEventRecurrenceUpdated", calendar, actor_id, event.id)
        return rule

    async def create_exception(
        self,
        organization_id: uuid.UUID,
        event_id: uuid.UUID,
        body: RecurrenceExceptionCreate,
        actor_id: uuid.UUID,
    ) -> CalendarEvent:
        calendar, parent = await self.get_event(organization_id, event_id)
        rule = await self.recurrence(organization_id, event_id)
        if rule is None:
            raise ValidationError("Event is not recurring")
        occurrence = self.timezones.to_utc(body.occurrence_start, parent.timezone)
        exception_key = occurrence.date().isoformat()
        if exception_key not in rule.exception_dates:
            rule.exception_dates = [*rule.exception_dates, exception_key]
        values = body.model_dump(exclude_unset=True, exclude={"occurrence_start"})
        start = values.pop("start_datetime", occurrence)
        duration = parent.end_datetime - parent.start_datetime
        end = values.pop("end_datetime", start + duration)
        exception = CalendarEvent(
            calendar_id=parent.calendar_id,
            title=str(values.pop("title", parent.title)),
            description=values.pop("description", parent.description),
            start_datetime=self.timezones.to_utc(start, parent.timezone),
            end_datetime=self.timezones.to_utc(end, parent.timezone),
            timezone=str(values.pop("timezone", parent.timezone)),
            status=values.pop("status", parent.status),
            visibility=values.pop("visibility", parent.visibility),
            all_day=bool(values.pop("all_day", parent.all_day)),
            category_id=values.pop("category_id", parent.category_id),
            recurrence_parent_id=parent.id,
            original_start_datetime=occurrence,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(exception)
        await self.session.flush()
        await self._record("CalendarEventExceptionCreated", calendar, actor_id, exception.id)
        return exception

    async def export_ics(self, organization_id: uuid.UUID, calendar_id: uuid.UUID) -> str:
        calendar = await self.get(organization_id, calendar_id)
        events = await self.list_events(organization_id, calendar_id, None, None)
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//MeetingHQ//Calendar//EN",
            f"X-WR-CALNAME:{self._ics_escape(calendar.name)}",
        ]
        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@meetinghq",
                    f"DTSTART:{self._ics_datetime(event.start_datetime)}",
                    f"DTEND:{self._ics_datetime(event.end_datetime)}",
                    f"SUMMARY:{self._ics_escape(event.title)}",
                    f"DESCRIPTION:{self._ics_escape(event.description or '')}",
                    f"STATUS:{event.status.value.upper()}",
                    "END:VEVENT",
                ]
            )
        lines.extend(["END:VCALENDAR", ""])
        return "\r\n".join(lines)

    async def import_ics(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        payload: str,
        actor_id: uuid.UUID,
    ) -> list[CalendarEvent]:
        await self.get(organization_id, calendar_id)
        imported: list[CalendarEvent] = []
        for block in payload.replace("\r\n ", "").split("BEGIN:VEVENT")[1:]:
            content = block.split("END:VEVENT", 1)[0]
            fields: dict[str, str] = {}
            for line in content.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.split(";", 1)[0]] = value
            if not {"DTSTART", "DTEND", "SUMMARY"}.issubset(fields):
                continue
            imported.append(
                await self.create_event(
                    organization_id,
                    calendar_id,
                    EventCreate(
                        title=self._ics_unescape(fields["SUMMARY"]),
                        description=self._ics_unescape(fields.get("DESCRIPTION", "")) or None,
                        start_datetime=self._parse_ics_datetime(fields["DTSTART"]),
                        end_datetime=self._parse_ics_datetime(fields["DTEND"]),
                        timezone="UTC",
                    ),
                    actor_id,
                )
            )
        if not imported:
            raise ValidationError("ICS file does not contain any importable events")
        return imported

    async def list_shares(
        self, organization_id: uuid.UUID, calendar_id: uuid.UUID
    ) -> list[CalendarShare]:
        await self.get(organization_id, calendar_id)
        return list(
            (
                await self.session.scalars(
                    select(CalendarShare)
                    .where(CalendarShare.calendar_id == calendar_id)
                    .order_by(CalendarShare.created_at)
                )
            ).all()
        )

    async def share(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        user_id: uuid.UUID,
        permission: str,
        actor_id: uuid.UUID,
    ) -> CalendarShare:
        calendar = await self.get(organization_id, calendar_id)
        user_exists = await self.session.scalar(
            select(User.id).where(
                User.id == user_id,
                User.organization_id == organization_id,
            )
        )
        if user_exists is None:
            raise NotFoundError("User not found")
        share = await self.session.scalar(
            select(CalendarShare).where(
                CalendarShare.calendar_id == calendar_id,
                CalendarShare.user_id == user_id,
            )
        )
        if share is None:
            share = CalendarShare(
                calendar_id=calendar_id,
                user_id=user_id,
                permission=permission,
                shared_by=actor_id,
            )
            self.session.add(share)
            await self.session.flush()
        else:
            share.permission = permission
            share.shared_by = actor_id
        await self._record("CalendarShared", calendar, actor_id, share.id)
        return share

    async def revoke_share(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        share_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        calendar = await self.get(organization_id, calendar_id)
        share = await self.session.scalar(
            select(CalendarShare).where(
                CalendarShare.id == share_id,
                CalendarShare.calendar_id == calendar_id,
            )
        )
        if share is None:
            raise NotFoundError("Calendar share not found")
        await self.session.delete(share)
        await self._record("CalendarShareRevoked", calendar, actor_id, share_id)

    async def list_categories(self, organization_id: uuid.UUID) -> list[EventCategory]:
        return list(
            (
                await self.session.scalars(
                    select(EventCategory)
                    .where(EventCategory.organization_id == organization_id)
                    .order_by(EventCategory.name)
                )
            ).all()
        )

    async def create_category(
        self,
        organization_id: uuid.UUID,
        body: EventCategoryCreate,
        actor_id: uuid.UUID,
    ) -> EventCategory:
        existing = await self.session.scalar(
            select(EventCategory.id).where(
                EventCategory.organization_id == organization_id,
                EventCategory.name == body.name,
            )
        )
        if existing is not None:
            raise ConflictError("An event category with this name already exists")
        category = EventCategory(
            organization_id=organization_id,
            created_by=actor_id,
            **body.model_dump(),
        )
        self.session.add(category)
        await self.session.flush()
        append_audit(
            self.session,
            organization_id,
            actor_id,
            "EventCategoryCreated",
            "event_category",
            category.id,
        )
        return category

    @staticmethod
    def _ics_datetime(value: datetime) -> str:
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _parse_ics_datetime(value: str) -> datetime:
        try:
            parsed = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
        except ValueError as exc:
            raise ValidationError("ICS contains an unsupported date format") from exc
        return parsed.replace(tzinfo=UTC)

    @staticmethod
    def _ics_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,")

    @staticmethod
    def _ics_unescape(value: str) -> str:
        return value.replace("\\n", "\n").replace("\\,", ",").replace("\\\\", "\\")

    async def _record(
        self,
        name: str,
        calendar: Calendar,
        actor_id: uuid.UUID,
        aggregate_id: uuid.UUID | None = None,
    ) -> None:
        resource_id = aggregate_id or calendar.id
        await self.events.publish(
            DomainEvent(
                name=name,
                organization_id=calendar.organization_id,
                workspace_id=calendar.workspace_id,
                actor_id=actor_id,
                aggregate_type="calendar" if aggregate_id is None else "calendar_event",
                aggregate_id=resource_id,
            )
        )
        append_audit(
            self.session, calendar.organization_id, actor_id, name, "calendar", resource_id
        )

    async def _require_category(self, organization_id: uuid.UUID, category_id: uuid.UUID) -> None:
        category = await self.session.scalar(
            select(EventCategory.id).where(
                EventCategory.id == category_id,
                EventCategory.organization_id == organization_id,
            )
        )
        if category is None:
            raise NotFoundError("Event category not found")


class CalendarRulesService:
    """Availability, busy block, and holiday use cases."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = TransactionalDomainEventPublisher(session)
        self.calendars = CalendarService(session, self.events)

    async def list_availability(
        self, organization_id: uuid.UUID, calendar_id: uuid.UUID
    ) -> list[AvailabilityRule]:
        await self.calendars.get(organization_id, calendar_id)
        return list(
            (
                await self.session.scalars(
                    select(AvailabilityRule)
                    .where(AvailabilityRule.calendar_id == calendar_id)
                    .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
                )
            ).all()
        )

    async def create_availability(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        body: AvailabilityCreate,
        actor_id: uuid.UUID,
    ) -> AvailabilityRule:
        calendar = await self.calendars.get(organization_id, calendar_id)
        rule = AvailabilityRule(calendar_id=calendar_id, **body.model_dump())
        self.session.add(rule)
        await self.session.flush()
        await self.events.publish(
            DomainEvent(
                name="AvailabilityUpdated",
                organization_id=organization_id,
                workspace_id=calendar.workspace_id,
                actor_id=actor_id,
                aggregate_type="availability_rule",
                aggregate_id=rule.id,
            )
        )
        append_audit(
            self.session,
            organization_id,
            actor_id,
            "AvailabilityUpdated",
            "availability_rule",
            rule.id,
        )
        return rule

    async def update_availability(
        self,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        body: AvailabilityCreate,
        actor_id: uuid.UUID,
    ) -> AvailabilityRule:
        rule = await self.session.scalar(
            select(AvailabilityRule)
            .join(Calendar, Calendar.id == AvailabilityRule.calendar_id)
            .where(
                AvailabilityRule.id == rule_id,
                Calendar.organization_id == organization_id,
            )
        )
        if rule is None:
            raise NotFoundError("Availability rule not found")
        for field, value in body.model_dump().items():
            setattr(rule, field, value)
        append_audit(
            self.session,
            organization_id,
            actor_id,
            "AvailabilityUpdated",
            "availability_rule",
            rule.id,
        )
        return rule

    async def delete_availability(
        self, organization_id: uuid.UUID, rule_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        rule = await self.update_availability(
            organization_id,
            rule_id,
            AvailabilityCreate(weekday=0, start_time=time(0), end_time=time(0, 1)),
            actor_id,
        )
        await self.session.delete(rule)

    async def list_busy(
        self, organization_id: uuid.UUID, calendar_id: uuid.UUID
    ) -> list[BusyBlock]:
        await self.calendars.get(organization_id, calendar_id)
        return list(
            (
                await self.session.scalars(
                    select(BusyBlock)
                    .where(BusyBlock.calendar_id == calendar_id)
                    .order_by(BusyBlock.start_datetime)
                )
            ).all()
        )

    async def create_busy(
        self,
        organization_id: uuid.UUID,
        calendar_id: uuid.UUID,
        body: BusyBlockCreate,
        actor_id: uuid.UUID,
    ) -> BusyBlock:
        await self.calendars.get(organization_id, calendar_id)
        block = BusyBlock(calendar_id=calendar_id, **body.model_dump())
        self.session.add(block)
        await self.session.flush()
        append_audit(
            self.session, organization_id, actor_id, "BusyBlockCreated", "busy_block", block.id
        )
        return block

    async def update_busy(
        self,
        organization_id: uuid.UUID,
        block_id: uuid.UUID,
        body: BusyBlockCreate,
        actor_id: uuid.UUID,
    ) -> BusyBlock:
        block = await self.session.scalar(
            select(BusyBlock)
            .join(Calendar, Calendar.id == BusyBlock.calendar_id)
            .where(BusyBlock.id == block_id, Calendar.organization_id == organization_id)
        )
        if block is None:
            raise NotFoundError("Busy block not found")
        for field, value in body.model_dump().items():
            setattr(block, field, value)
        append_audit(
            self.session, organization_id, actor_id, "BusyBlockUpdated", "busy_block", block.id
        )
        return block

    async def delete_busy(
        self, organization_id: uuid.UUID, block_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        block = await self.update_busy(
            organization_id,
            block_id,
            BusyBlockCreate(
                start_datetime=datetime.now(UTC),
                end_datetime=datetime.now(UTC) + timedelta(minutes=1),
            ),
            actor_id,
        )
        await self.session.delete(block)

    async def list_holidays(self, organization_id: uuid.UUID) -> list[Holiday]:
        return list(
            (
                await self.session.scalars(
                    select(Holiday)
                    .where(Holiday.organization_id == organization_id)
                    .order_by(Holiday.date)
                )
            ).all()
        )

    async def create_holiday(
        self, organization_id: uuid.UUID, body: HolidayCreate, actor_id: uuid.UUID
    ) -> Holiday:
        holiday = Holiday(organization_id=organization_id, **body.model_dump())
        self.session.add(holiday)
        await self.session.flush()
        await self.events.publish(
            DomainEvent(
                name="HolidayCreated",
                organization_id=organization_id,
                actor_id=actor_id,
                aggregate_type="holiday",
                aggregate_id=holiday.id,
            )
        )
        append_audit(
            self.session, organization_id, actor_id, "HolidayCreated", "holiday", holiday.id
        )
        return holiday

    async def update_holiday(
        self,
        organization_id: uuid.UUID,
        holiday_id: uuid.UUID,
        body: HolidayCreate,
        actor_id: uuid.UUID,
    ) -> Holiday:
        holiday = await self.session.scalar(
            select(Holiday).where(
                Holiday.id == holiday_id,
                Holiday.organization_id == organization_id,
            )
        )
        if holiday is None:
            raise NotFoundError("Holiday not found")
        for field, value in body.model_dump().items():
            setattr(holiday, field, value)
        append_audit(
            self.session, organization_id, actor_id, "HolidayUpdated", "holiday", holiday.id
        )
        return holiday

    async def delete_holiday(
        self, organization_id: uuid.UUID, holiday_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        holiday = await self.update_holiday(
            organization_id,
            holiday_id,
            HolidayCreate(name="Deleted", date=date.today()),
            actor_id,
        )
        await self.session.delete(holiday)


class ResourceService:
    """First-class resource calendars and reservations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = TransactionalDomainEventPublisher(session)

    async def list(self, organization_id: uuid.UUID) -> list[Resource]:
        return list(
            (
                await self.session.scalars(
                    select(Resource).where(
                        Resource.organization_id == organization_id,
                        Resource.deleted_at.is_(None),
                    )
                )
            ).all()
        )

    async def create(
        self, organization_id: uuid.UUID, body: ResourceCreate, actor_id: uuid.UUID
    ) -> Resource:
        calendar = await CalendarService(self.session, self.events).create(
            organization_id,
            CalendarCreate(
                workspace_id=body.workspace_id,
                name=f"{body.name} bookings",
                type=CalendarType.RESOURCE,
                timezone=body.timezone,
            ),
            actor_id,
        )
        resource = Resource(
            organization_id=organization_id,
            calendar_id=calendar.id,
            **body.model_dump(exclude={"timezone"}),
        )
        self.session.add(resource)
        await self.session.flush()
        await self.events.publish(
            DomainEvent(
                name="ResourceCreated",
                organization_id=organization_id,
                workspace_id=body.workspace_id,
                actor_id=actor_id,
                aggregate_type="resource",
                aggregate_id=resource.id,
            )
        )
        append_audit(
            self.session, organization_id, actor_id, "ResourceCreated", "resource", resource.id
        )
        return resource

    async def reserve(
        self, organization_id: uuid.UUID, body: ReservationCreate, actor_id: uuid.UUID
    ) -> ResourceReservation:
        repository = SchedulingRepository(self.session)
        if not await repository.resource_owned(organization_id, body.resource_id):
            raise NotFoundError("Resource not found")
        conflicts = await repository.busy_ranges(
            [], [body.resource_id], body.start_datetime, body.end_datetime
        )
        result = SchedulingEngine().validate(
            TimeRange(body.start_datetime, body.end_datetime),
            [TimeRange(*item) for item in conflicts],
        )
        if not result.valid:
            raise ConflictError("Resource is unavailable")
        reservation = ResourceReservation(created_by=actor_id, **body.model_dump())
        self.session.add(reservation)
        await self.session.flush()
        await self.events.publish(
            DomainEvent(
                name="ReservationCreated",
                organization_id=organization_id,
                actor_id=actor_id,
                aggregate_type="reservation",
                aggregate_id=reservation.id,
            )
        )
        append_audit(
            self.session,
            organization_id,
            actor_id,
            "ReservationCreated",
            "reservation",
            reservation.id,
        )
        return reservation

    async def update(
        self,
        organization_id: uuid.UUID,
        resource_id: uuid.UUID,
        body: ResourceCreate,
        actor_id: uuid.UUID,
    ) -> Resource:
        resource = await self.session.scalar(
            select(Resource).where(
                Resource.id == resource_id,
                Resource.organization_id == organization_id,
                Resource.deleted_at.is_(None),
            )
        )
        if resource is None:
            raise NotFoundError("Resource not found")
        for field, value in body.model_dump(exclude={"timezone"}).items():
            setattr(resource, field, value)
        append_audit(
            self.session, organization_id, actor_id, "ResourceUpdated", "resource", resource.id
        )
        return resource

    async def delete(
        self, organization_id: uuid.UUID, resource_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        resource = await self.session.scalar(
            select(Resource).where(
                Resource.id == resource_id,
                Resource.organization_id == organization_id,
                Resource.deleted_at.is_(None),
            )
        )
        if resource is None:
            raise NotFoundError("Resource not found")
        resource.soft_delete(actor_id)
        append_audit(
            self.session, organization_id, actor_id, "ResourceDeleted", "resource", resource.id
        )

    async def cancel(
        self, organization_id: uuid.UUID, reservation_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        reservation = await self.session.scalar(
            select(ResourceReservation)
            .join(Resource, Resource.id == ResourceReservation.resource_id)
            .where(
                ResourceReservation.id == reservation_id,
                Resource.organization_id == organization_id,
            )
        )
        if reservation is None:
            raise NotFoundError("Reservation not found")
        reservation.cancelled_at = datetime.now(UTC)
        await self.events.publish(
            DomainEvent(
                name="ReservationCancelled",
                organization_id=organization_id,
                actor_id=actor_id,
                aggregate_type="reservation",
                aggregate_id=reservation.id,
            )
        )
        append_audit(
            self.session,
            organization_id,
            actor_id,
            "ReservationCancelled",
            "reservation",
            reservation.id,
        )


class SchedulingService:
    """Persistence-backed adapter around the pure scheduling engine."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = SchedulingRepository(session)
        self.engine = SchedulingEngine()
        self.timezones = TimezoneService()

    async def validate(
        self, organization_id: uuid.UUID, body: ScheduleValidationRequest
    ) -> ValidationResult:
        await self._validate_scope(organization_id, body.calendar_ids, body.resource_ids)
        start = self.timezones.to_utc(body.start_datetime, body.timezone)
        end = self.timezones.to_utc(body.end_datetime, body.timezone)
        ranges = await self.repository.busy_ranges(body.calendar_ids, body.resource_ids, start, end)
        return self.engine.validate(
            TimeRange(start, end),
            [TimeRange(*item) for item in ranges],
            SchedulingPolicy(
                buffer_before=timedelta(minutes=body.buffer_minutes),
                buffer_after=timedelta(minutes=body.buffer_minutes),
            ),
        )

    async def suggest(
        self, organization_id: uuid.UUID, body: SlotSuggestionRequest
    ) -> list[TimeRange]:
        await self._validate_scope(organization_id, body.calendar_ids, body.resource_ids)
        start = self.timezones.to_utc(body.start_datetime, body.timezone)
        end = self.timezones.to_utc(body.search_end, body.timezone)
        ranges = await self.repository.busy_ranges(body.calendar_ids, body.resource_ids, start, end)
        return self.engine.suggest(
            TimeRange(start, end),
            timedelta(minutes=body.duration_minutes),
            [TimeRange(*item) for item in ranges],
            (time(8), time(18)),
            limit=body.limit,
            policy=SchedulingPolicy(
                buffer_before=timedelta(minutes=body.buffer_minutes),
                buffer_after=timedelta(minutes=body.buffer_minutes),
            ),
        )

    async def _validate_scope(
        self,
        organization_id: uuid.UUID,
        calendar_ids: list[uuid.UUID],
        resource_ids: list[uuid.UUID],
    ) -> None:
        for calendar_id in calendar_ids:
            if not await self.repository.calendar_owned(organization_id, calendar_id):
                raise NotFoundError("Calendar not found")
        for resource_id in resource_ids:
            if not await self.repository.resource_owned(organization_id, resource_id):
                raise NotFoundError("Resource not found")
