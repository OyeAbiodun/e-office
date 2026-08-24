"""Meeting aggregate application service."""

# ruff: noqa: E501

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.calendar.models import (
    Calendar,
    CalendarEvent,
    CalendarType,
    EventStatus,
    RecurrenceRule,
    Visibility,
)
from meetinghq_api.modules.calendar.schemas import (
    CalendarCreate,
    EventCreate,
    RecurrenceRuleInput,
    ReservationCreate,
    ScheduleValidationRequest,
)
from meetinghq_api.modules.calendar.service import (
    CalendarService,
    ResourceService,
    SchedulingService,
)
from meetinghq_api.modules.meetings.models import (
    AttendanceStatus,
    Meeting,
    MeetingActionItem,
    MeetingAgenda,
    MeetingArtifact,
    MeetingAttendanceEvent,
    MeetingAttendee,
    MeetingDecision,
    MeetingFollowUp,
    MeetingNote,
    MeetingPresenterControl,
    MeetingRecording,
    MeetingStatus,
    MeetingTemplate,
)
from meetinghq_api.modules.meetings.repository import MeetingRepository
from meetinghq_api.modules.meetings.schemas import (
    ActionItemInput,
    AgendaInput,
    ArtifactInput,
    AttendanceEventInput,
    AttendeeCreate,
    DecisionInput,
    FollowUpInput,
    MeetingCreate,
    MeetingUpdate,
    NoteInput,
    PresenterControlInput,
    RecordingInput,
    RescheduleRequest,
    TemplateInput,
)
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.events import DomainEvent
from meetinghq_api.shared.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

TRANSITIONS: dict[MeetingStatus, frozenset[MeetingStatus]] = {
    MeetingStatus.DRAFT: frozenset({MeetingStatus.SCHEDULED, MeetingStatus.CANCELLED}),
    MeetingStatus.SCHEDULED: frozenset(
        {MeetingStatus.CONFIRMED, MeetingStatus.IN_PROGRESS, MeetingStatus.CANCELLED}
    ),
    MeetingStatus.CONFIRMED: frozenset({MeetingStatus.IN_PROGRESS, MeetingStatus.CANCELLED}),
    MeetingStatus.IN_PROGRESS: frozenset({MeetingStatus.COMPLETED, MeetingStatus.CANCELLED}),
    MeetingStatus.COMPLETED: frozenset({MeetingStatus.ARCHIVED}),
    MeetingStatus.CANCELLED: frozenset({MeetingStatus.ARCHIVED}),
    MeetingStatus.ARCHIVED: frozenset(),
}


def serialize(model: object) -> dict[str, object]:
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns  # type: ignore[attr-defined]
    }


class MeetingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = MeetingRepository(session)
        self.events = TransactionalDomainEventPublisher(session)
        self.notifications = NotificationService(session, get_settings())

    async def get(self, organization_id: uuid.UUID, meeting_id: uuid.UUID) -> Meeting:
        meeting = await self.repository.get(organization_id, meeting_id)
        if meeting is None:
            raise NotFoundError("Meeting not found")
        return meeting

    @staticmethod
    def _require_organizer(meeting: Meeting, actor_id: uuid.UUID, allow_manage: bool) -> None:
        if meeting.organizer_id != actor_id and not allow_manage:
            raise AuthorizationError("Only the organizer or a meeting administrator can modify it")

    async def find(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
    ) -> list[Meeting]:
        meetings = await self.repository.involved(organization_id, user_id)
        return [
            meeting
            for meeting in meetings
            if (start is None or meeting.end_datetime >= start)
            and (end is None or meeting.start_datetime <= end)
            and (status is None or meeting.status == status)
        ]

    async def detail(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, object]:
        meeting = await self.get(organization_id, meeting_id)
        involved = await self.session.scalar(
            select(MeetingAttendee.id).where(
                MeetingAttendee.meeting_id == meeting.id,
                MeetingAttendee.user_id == user_id,
            )
        )
        if meeting.organizer_id != user_id and involved is None:
            raise NotFoundError("Meeting not found")
        result = serialize(meeting)
        collections: dict[str, tuple[Any, Any]] = {
            "attendees": (MeetingAttendee, MeetingAttendee.user_id),
            "agenda": (MeetingAgenda, MeetingAgenda.sort_order),
            "decisions": (MeetingDecision, MeetingDecision.id),
            "action_items": (MeetingActionItem, MeetingActionItem.id),
            "notes": (MeetingNote, MeetingNote.created_at),
            "artifacts": (MeetingArtifact, MeetingArtifact.created_at),
            "recordings": (MeetingRecording, MeetingRecording.created_at),
            "attendance_events": (
                MeetingAttendanceEvent,
                MeetingAttendanceEvent.occurred_at,
            ),
            "presenter_controls": (
                MeetingPresenterControl,
                MeetingPresenterControl.granted_at,
            ),
            "follow_ups": (MeetingFollowUp, MeetingFollowUp.scheduled_for),
        }
        for name, (model, order) in collections.items():
            rows = (
                await self.session.scalars(
                    select(model).where(model.meeting_id == meeting.id).order_by(order)
                )
            ).all()
            result[name] = [serialize(row) for row in rows]
        attendee_rows = (
            await self.session.execute(
                select(MeetingAttendee, User)
                .join(User, User.id == MeetingAttendee.user_id)
                .where(
                    MeetingAttendee.meeting_id == meeting.id,
                    User.organization_id == organization_id,
                )
                .order_by(User.display_name)
            )
        ).all()
        result["attendees"] = [
            {
                **serialize(attendee),
                "display_name": participant.display_name,
                "email": participant.email,
                "avatar_url": participant.avatar_url,
            }
            for attendee, participant in attendee_rows
        ]
        return result

    async def create(
        self, organization_id: uuid.UUID, body: MeetingCreate, actor_id: uuid.UUID
    ) -> Meeting:
        calendar = await self._calendar(organization_id, body, actor_id)
        validation = await SchedulingService(self.session).validate(
            organization_id,
            ScheduleValidationRequest(
                calendar_ids=[calendar.id],
                resource_ids=[body.room_id] if body.room_id else [],
                start_datetime=body.start_datetime,
                end_datetime=body.end_datetime,
                timezone=body.timezone,
            ),
        )
        if not validation.valid:
            raise ConflictError("; ".join(validation.reasons))
        event = await CalendarService(self.session).create_event(
            organization_id,
            calendar.id,
            EventCreate(
                title=body.title,
                description=body.description,
                start_datetime=body.start_datetime,
                end_datetime=body.end_datetime,
                timezone=body.timezone,
                visibility=Visibility(body.visibility),
                recurrence=body.recurrence,
            ),
            actor_id,
        )
        meeting = Meeting(
            organization_id=organization_id,
            organizer_id=actor_id,
            calendar_event_id=event.id,
            status=MeetingStatus.SCHEDULED,
            **body.model_dump(
                exclude={
                    "calendar_id",
                    "attendee_ids",
                    "cohost_ids",
                    "recurrence",
                    "start_datetime",
                    "end_datetime",
                }
            ),
            recurrence=body.recurrence.model_dump(mode="json") if body.recurrence else None,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
        )
        self.session.add(meeting)
        await self.session.flush()
        event.meeting_id = meeting.id
        attendee_ids = set(body.attendee_ids) | set(body.cohost_ids) | {actor_id}
        await self._validate_users(organization_id, attendee_ids)
        for user_id in attendee_ids:
            self.session.add(
                MeetingAttendee(
                    meeting_id=meeting.id,
                    user_id=user_id,
                    role=(
                        "organizer"
                        if user_id == actor_id
                        else "cohost" if user_id in body.cohost_ids else "attendee"
                    ),
                    attendance_status=(
                        AttendanceStatus.ACCEPTED
                        if user_id == actor_id
                        else AttendanceStatus.PENDING
                    ),
                )
            )
            if user_id != actor_id:
                await self._record("AttendeeInvited", meeting, actor_id, {"user_id": str(user_id)})
                await self._create_participant_event(meeting, user_id, body.recurrence)
        if body.room_id:
            await ResourceService(self.session).reserve(
                organization_id,
                ReservationCreate(
                    resource_id=body.room_id,
                    calendar_event_id=event.id,
                    start_datetime=event.start_datetime,
                    end_datetime=event.end_datetime,
                ),
                actor_id,
            )
        await self._record("MeetingCreated", meeting, actor_id)
        organizer = await self.session.get(User, actor_id)
        if organizer is None:
            raise NotFoundError("Meeting organizer not found")
        await self.notifications.invite_participants(meeting, organizer, attendee_ids - {actor_id})
        await self.notifications.schedule_reminders(meeting, {actor_id})
        return meeting

    async def update(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: MeetingUpdate,
        actor_id: uuid.UUID,
        allow_manage: bool = False,
    ) -> Meeting:
        meeting = await self.get(organization_id, meeting_id)
        self._require_organizer(meeting, actor_id, allow_manage)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(meeting, field, value)
        events = list(
            (
                await self.session.scalars(
                    select(CalendarEvent).where(CalendarEvent.meeting_id == meeting.id)
                )
            ).all()
        )
        for calendar_event in events:
            calendar_event.title = meeting.title
            calendar_event.description = meeting.description
        await self.notifications.notify_participants(
            meeting,
            "meeting_updated",
            f"Meeting updated: {meeting.title}",
            f"{meeting.title} was updated. Open MeetingHQ for the latest details.",
            calendar_method="REQUEST",
        )
        await self._record("MeetingUpdated", meeting, actor_id)
        meeting.updated_at = datetime.now(UTC)
        return meeting

    async def transition(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        target: MeetingStatus,
        actor_id: uuid.UUID,
        allow_manage: bool = False,
    ) -> Meeting:
        meeting = await self.get(organization_id, meeting_id)
        self._require_organizer(meeting, actor_id, allow_manage)
        if target not in TRANSITIONS[meeting.status]:
            raise ValidationError(f"Cannot transition meeting from {meeting.status} to {target}")
        meeting.status = target
        if target == MeetingStatus.CANCELLED and meeting.calendar_event_id:
            events = (
                await self.session.scalars(
                    select(CalendarEvent).where(CalendarEvent.meeting_id == meeting.id)
                )
            ).all()
            for event in events:
                event.status = EventStatus.CANCELLED
            await self.notifications.notify_participants(
                meeting,
                "meeting_cancelled",
                f"Meeting cancelled: {meeting.title}",
                f"{meeting.title} scheduled for {meeting.start_datetime.isoformat()} was cancelled.",
                calendar_method="CANCEL",
            )
        names = {
            MeetingStatus.CANCELLED: "MeetingCancelled",
            MeetingStatus.IN_PROGRESS: "MeetingStarted",
            MeetingStatus.COMPLETED: "MeetingCompleted",
        }
        await self._record(
            names.get(target, "MeetingUpdated"), meeting, actor_id, {"status": target}
        )
        meeting.updated_at = datetime.now(UTC)
        return meeting

    async def reschedule(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: RescheduleRequest,
        actor_id: uuid.UUID,
        allow_manage: bool = False,
    ) -> Meeting:
        meeting = await self.get(organization_id, meeting_id)
        self._require_organizer(meeting, actor_id, allow_manage)
        if meeting.status in {
            MeetingStatus.CANCELLED,
            MeetingStatus.COMPLETED,
            MeetingStatus.ARCHIVED,
        }:
            raise ValidationError("This meeting can no longer be rescheduled")
        old_events = list(
            (
                await self.session.scalars(
                    select(CalendarEvent).where(CalendarEvent.meeting_id == meeting.id)
                )
            ).all()
        )
        old_event = next(
            (item for item in old_events if item.id == meeting.calendar_event_id),
            None,
        )
        for existing_event in old_events:
            existing_event.status = EventStatus.CANCELLED
        calendar = (
            await self.session.get(Calendar, body.calendar_id)
            if body.calendar_id
            else await self.session.get(Calendar, old_event.calendar_id if old_event else None)
        )
        if calendar is None or calendar.organization_id != organization_id:
            raise NotFoundError("Calendar not found")
        validation = await SchedulingService(self.session).validate(
            organization_id,
            ScheduleValidationRequest(
                calendar_ids=[calendar.id],
                resource_ids=[body.room_id] if body.room_id else [],
                start_datetime=body.start_datetime,
                end_datetime=body.end_datetime,
                timezone=body.timezone,
            ),
        )
        if not validation.valid:
            for existing_event in old_events:
                existing_event.status = EventStatus.CONFIRMED
            raise ConflictError("; ".join(validation.reasons))
        event = await CalendarService(self.session).create_event(
            organization_id,
            calendar.id,
            EventCreate(
                title=meeting.title,
                description=meeting.description,
                start_datetime=body.start_datetime,
                end_datetime=body.end_datetime,
                timezone=body.timezone,
                visibility=Visibility(meeting.visibility),
            ),
            actor_id,
        )
        meeting.calendar_event_id = event.id
        event.meeting_id = meeting.id
        meeting.room_id = body.room_id
        meeting.start_datetime = event.start_datetime
        meeting.end_datetime = event.end_datetime
        meeting.timezone = body.timezone
        participant_ids = set(
            (
                await self.session.scalars(
                    select(MeetingAttendee.user_id).where(
                        MeetingAttendee.meeting_id == meeting.id,
                        MeetingAttendee.user_id != actor_id,
                    )
                )
            ).all()
        )
        for participant_id in participant_ids:
            await self._create_participant_event(meeting, participant_id, None)
        await self.notifications.notify_participants(
            meeting,
            "meeting_updated",
            f"Meeting rescheduled: {meeting.title}",
            f"{meeting.title} now starts at {meeting.start_datetime.isoformat()} ({meeting.timezone}).",
            calendar_method="REQUEST",
        )
        await self._record("MeetingRescheduled", meeting, actor_id)
        meeting.updated_at = datetime.now(UTC)
        return meeting

    async def duplicate(
        self, organization_id: uuid.UUID, meeting_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Meeting:
        meeting = await self.get(organization_id, meeting_id)
        calendar = await self.session.get(CalendarEvent, meeting.calendar_event_id)
        attendees = list(
            (
                await self.session.scalars(
                    select(MeetingAttendee.user_id).where(MeetingAttendee.meeting_id == meeting.id)
                )
            ).all()
        )
        return await self.create(
            organization_id,
            MeetingCreate(
                workspace_id=meeting.workspace_id,
                calendar_id=calendar.calendar_id if calendar else None,
                meeting_template_id=meeting.meeting_template_id,
                title=f"Copy of {meeting.title}",
                description=meeting.description,
                meeting_type=meeting.meeting_type,
                location_type=meeting.location_type,
                meeting_url=meeting.meeting_url,
                start_datetime=meeting.start_datetime + timedelta(days=7),
                end_datetime=meeting.end_datetime + timedelta(days=7),
                timezone=meeting.timezone,
                visibility=meeting.visibility,
                attendee_ids=attendees,
            ),
            actor_id,
        )

    async def add_attendee(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: AttendeeCreate,
        actor_id: uuid.UUID,
    ) -> MeetingAttendee:
        meeting = await self.get(organization_id, meeting_id)
        await self._validate_users(organization_id, {body.user_id})
        existing = await self.session.scalar(
            select(MeetingAttendee).where(
                MeetingAttendee.meeting_id == meeting.id, MeetingAttendee.user_id == body.user_id
            )
        )
        if existing:
            return existing
        attendee = MeetingAttendee(meeting_id=meeting.id, **body.model_dump())
        self.session.add(attendee)
        await self.session.flush()
        await self._record("AttendeeInvited", meeting, actor_id, {"user_id": str(body.user_id)})
        await self._create_participant_event(meeting, body.user_id, None)
        organizer = await self.session.get(User, meeting.organizer_id)
        if organizer is None:
            raise NotFoundError("Meeting organizer not found")
        await self.notifications.invite_participants(meeting, organizer, {body.user_id})
        return attendee

    async def rsvp(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        user_id: uuid.UUID,
        status: AttendanceStatus,
    ) -> MeetingAttendee:
        meeting = await self.get(organization_id, meeting_id)
        attendee = await self.session.scalar(
            select(MeetingAttendee).where(
                MeetingAttendee.meeting_id == meeting.id, MeetingAttendee.user_id == user_id
            )
        )
        if attendee is None:
            raise NotFoundError("Meeting invitation not found")
        attendee.attendance_status = status
        now = datetime.now(UTC)
        if status == AttendanceStatus.JOINED:
            attendee.joined_at = now
        if status == AttendanceStatus.LEFT:
            attendee.left_at = now
        event = {
            AttendanceStatus.ACCEPTED: "AttendeeAccepted",
            AttendanceStatus.DECLINED: "AttendeeDeclined",
        }.get(status, "MeetingUpdated")
        await self._record(event, meeting, user_id, {"attendance_status": status})
        responder = await self.session.get(User, user_id)
        await self.notifications.notify_organizer(
            meeting,
            "meeting_rsvp",
            f"{responder.display_name if responder else 'A participant'} responded",
            f"RSVP status: {status.value}",
        )
        return attendee

    async def add_agenda(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: AgendaInput,
        actor_id: uuid.UUID,
    ) -> MeetingAgenda:
        meeting = await self.get(organization_id, meeting_id)
        agenda = MeetingAgenda(meeting_id=meeting.id, **body.model_dump())
        self.session.add(agenda)
        await self.session.flush()
        await self._record("AgendaUpdated", meeting, actor_id)
        return agenda

    async def reorder_agenda(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        ids: list[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> list[MeetingAgenda]:
        meeting = await self.get(organization_id, meeting_id)
        rows = list(
            (
                await self.session.scalars(
                    select(MeetingAgenda).where(MeetingAgenda.meeting_id == meeting.id)
                )
            ).all()
        )
        by_id = {row.id: row for row in rows}
        if set(ids) != set(by_id):
            raise ValidationError("Agenda order must contain every agenda item exactly once")
        for order, item_id in enumerate(ids):
            by_id[item_id].sort_order = order
        await self._record("AgendaUpdated", meeting, actor_id)
        return [by_id[item_id] for item_id in ids]

    async def add_decision(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: DecisionInput,
        actor_id: uuid.UUID,
    ) -> MeetingDecision:
        meeting = await self.get(organization_id, meeting_id)
        item = MeetingDecision(meeting_id=meeting.id, created_by=actor_id, **body.model_dump())
        self.session.add(item)
        await self.session.flush()
        await self._record("DecisionCreated", meeting, actor_id)
        return item

    async def add_action(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: ActionItemInput,
        actor_id: uuid.UUID,
    ) -> MeetingActionItem:
        meeting = await self.get(organization_id, meeting_id)
        if body.assigned_to:
            await self._validate_users(organization_id, {body.assigned_to})
        item = MeetingActionItem(meeting_id=meeting.id, **body.model_dump())
        if item.status == "completed":
            item.completed_at = datetime.now(UTC)
        self.session.add(item)
        await self.session.flush()
        await self._record("ActionItemCreated", meeting, actor_id)
        return item

    async def add_note(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: NoteInput,
        actor_id: uuid.UUID,
    ) -> MeetingNote:
        meeting = await self.get(organization_id, meeting_id)
        item = MeetingNote(meeting_id=meeting.id, author_id=actor_id, content=body.content)
        self.session.add(item)
        await self.session.flush()
        await self._record("MeetingUpdated", meeting, actor_id, {"note_id": str(item.id)})
        return item

    async def add_artifact(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: ArtifactInput,
        actor_id: uuid.UUID,
    ) -> MeetingArtifact:
        meeting = await self.get(organization_id, meeting_id)
        artifact = MeetingArtifact(meeting_id=meeting.id, created_by=actor_id, **body.model_dump())
        self.session.add(artifact)
        await self.session.flush()
        await self._record(
            "MeetingArtifactAdded",
            meeting,
            actor_id,
            {"artifact_id": str(artifact.id), "type": artifact.artifact_type},
        )
        return artifact

    async def add_recording(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: RecordingInput,
        actor_id: uuid.UUID,
    ) -> MeetingRecording:
        meeting = await self.get(organization_id, meeting_id)
        recording = MeetingRecording(
            meeting_id=meeting.id, created_by=actor_id, **body.model_dump()
        )
        self.session.add(recording)
        await self.session.flush()
        await self._record(
            "MeetingRecordingAdded",
            meeting,
            actor_id,
            {"recording_id": str(recording.id), "status": recording.status},
        )
        return recording

    async def attendance(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: AttendanceEventInput,
        actor_id: uuid.UUID,
    ) -> MeetingAttendanceEvent:
        meeting = await self.get(organization_id, meeting_id)
        attendee = await self.session.scalar(
            select(MeetingAttendee).where(
                MeetingAttendee.meeting_id == meeting.id,
                MeetingAttendee.user_id == body.user_id,
            )
        )
        if attendee is None:
            raise NotFoundError("Meeting attendee not found")
        occurred_at = body.occurred_at or datetime.now(UTC)
        event = MeetingAttendanceEvent(
            meeting_id=meeting.id,
            user_id=body.user_id,
            event_type=body.event_type,
            occurred_at=occurred_at,
            recorded_by=actor_id,
        )
        self.session.add(event)
        if body.event_type == "joined":
            attendee.joined_at = occurred_at
            attendee.attendance_status = AttendanceStatus.JOINED
        elif body.event_type == "left":
            attendee.left_at = occurred_at
            attendee.attendance_status = AttendanceStatus.LEFT
        else:
            attendee.attendance_status = AttendanceStatus.NO_SHOW
        await self.session.flush()
        await self._record(
            "MeetingAttendanceRecorded",
            meeting,
            actor_id,
            {"user_id": str(body.user_id), "event_type": body.event_type},
        )
        return event

    async def presenter_control(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: PresenterControlInput,
        actor_id: uuid.UUID,
    ) -> MeetingPresenterControl:
        meeting = await self.get(organization_id, meeting_id)
        await self._validate_users(organization_id, {body.user_id})
        control = await self.session.scalar(
            select(MeetingPresenterControl).where(
                MeetingPresenterControl.meeting_id == meeting.id,
                MeetingPresenterControl.user_id == body.user_id,
                MeetingPresenterControl.control == body.control,
                MeetingPresenterControl.revoked_at.is_(None),
            )
        )
        if control is None:
            control = MeetingPresenterControl(
                meeting_id=meeting.id,
                user_id=body.user_id,
                control=body.control,
                granted_by=actor_id,
            )
            self.session.add(control)
            await self.session.flush()
        control.revoked_at = None if body.enabled else datetime.now(UTC)
        await self._record(
            "MeetingPresenterControlUpdated",
            meeting,
            actor_id,
            {
                "user_id": str(body.user_id),
                "control": body.control,
                "enabled": body.enabled,
            },
        )
        return control

    async def schedule_follow_up(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        body: FollowUpInput,
        actor_id: uuid.UUID,
    ) -> MeetingFollowUp:
        meeting = await self.get(organization_id, meeting_id)
        follow_up = MeetingFollowUp(meeting_id=meeting.id, created_by=actor_id, **body.model_dump())
        self.session.add(follow_up)
        await self.session.flush()
        await self._record(
            "MeetingFollowUpScheduled",
            meeting,
            actor_id,
            {"follow_up_id": str(follow_up.id), "type": follow_up.follow_up_type},
        )
        return follow_up

    async def analytics(
        self, organization_id: uuid.UUID, meeting_id: uuid.UUID
    ) -> dict[str, int | float]:
        meeting = await self.get(organization_id, meeting_id)
        attendees = list(
            (
                await self.session.scalars(
                    select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting.id)
                )
            ).all()
        )
        joined = [attendee for attendee in attendees if attendee.joined_at is not None]
        minutes = [
            max(
                0.0,
                ((attendee.left_at or meeting.end_datetime) - attendee.joined_at).total_seconds()
                / 60,
            )
            for attendee in joined
            if attendee.joined_at is not None
        ]
        counts: dict[str, int] = {}
        count_models: dict[str, Any] = {
            "agenda_items": MeetingAgenda,
            "decisions": MeetingDecision,
            "action_items": MeetingActionItem,
        }
        for key, model in count_models.items():
            counts[key] = (
                await self.session.scalar(
                    select(func.count(model.id)).where(model.meeting_id == meeting.id)
                )
                or 0
            )
        completed_actions = (
            await self.session.scalar(
                select(func.count(MeetingActionItem.id)).where(
                    MeetingActionItem.meeting_id == meeting.id,
                    MeetingActionItem.status == "completed",
                )
            )
            or 0
        )
        follow_ups_pending = (
            await self.session.scalar(
                select(func.count(MeetingFollowUp.id)).where(
                    MeetingFollowUp.meeting_id == meeting.id,
                    MeetingFollowUp.status == "pending",
                )
            )
            or 0
        )
        return {
            "attendee_count": len(attendees),
            "joined_count": len(joined),
            "attendance_rate": round(len(joined) / len(attendees) * 100, 1) if attendees else 0.0,
            "average_minutes_attended": round(sum(minutes) / len(minutes), 1) if minutes else 0.0,
            **counts,
            "completed_actions": completed_actions,
            "follow_ups_pending": follow_ups_pending,
        }

    async def delete_item(
        self,
        organization_id: uuid.UUID,
        meeting_id: uuid.UUID,
        model: Any,
        item_id: uuid.UUID,
        actor_id: uuid.UUID,
        event: str,
    ) -> None:
        meeting = await self.get(organization_id, meeting_id)
        item = await self.session.scalar(
            select(model).where(model.id == item_id, model.meeting_id == meeting.id)
        )
        if item is None:
            raise NotFoundError("Meeting item not found")
        await self.session.delete(item)
        await self._record(event, meeting, actor_id)

    async def templates(self, organization_id: uuid.UUID) -> list[MeetingTemplate]:
        return list(
            (
                await self.session.scalars(
                    select(MeetingTemplate)
                    .where(MeetingTemplate.organization_id == organization_id)
                    .order_by(MeetingTemplate.name)
                )
            ).all()
        )

    async def create_template(
        self, organization_id: uuid.UUID, body: TemplateInput
    ) -> MeetingTemplate:
        item = MeetingTemplate(organization_id=organization_id, **body.model_dump())
        self.session.add(item)
        await self.session.flush()
        return item

    async def history(
        self, organization_id: uuid.UUID, meeting_id: uuid.UUID
    ) -> list[dict[str, object]]:
        from meetinghq_api.modules.events.models import DomainEventRecord

        await self.get(organization_id, meeting_id)
        rows = (
            await self.session.scalars(
                select(DomainEventRecord)
                .where(
                    DomainEventRecord.organization_id == organization_id,
                    DomainEventRecord.aggregate_type == "meeting",
                    DomainEventRecord.aggregate_id == meeting_id,
                )
                .order_by(DomainEventRecord.occurred_at.desc())
            )
        ).all()
        return [serialize(row) for row in rows]

    async def dashboard(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        now = datetime.now(UTC)
        meetings = await self.repository.involved(organization_id, user_id)
        today_end = datetime.combine(now.date(), time.max, tzinfo=UTC)
        today = [
            meeting
            for meeting in meetings
            if now
            <= meeting.start_datetime.replace(tzinfo=meeting.start_datetime.tzinfo or UTC)
            <= today_end
        ]
        upcoming = [
            meeting
            for meeting in meetings
            if meeting.start_datetime.replace(tzinfo=meeting.start_datetime.tzinfo or UTC)
            > today_end
            and meeting.status not in {MeetingStatus.CANCELLED, MeetingStatus.ARCHIVED}
        ][:6]
        recent = [
            meeting
            for meeting in meetings
            if meeting.end_datetime.replace(tzinfo=meeting.end_datetime.tzinfo or UTC) < now
        ][-6:]
        pending = (
            await self.session.scalar(
                select(func.count(MeetingAttendee.id))
                .join(Meeting)
                .where(
                    Meeting.organization_id == organization_id,
                    MeetingAttendee.user_id == user_id,
                    MeetingAttendee.attendance_status == AttendanceStatus.PENDING,
                )
            )
            or 0
        )
        actions = list(
            (
                await self.session.scalars(
                    select(MeetingActionItem)
                    .join(Meeting)
                    .where(
                        Meeting.organization_id == organization_id,
                        MeetingActionItem.assigned_to == user_id,
                        MeetingActionItem.status != "completed",
                    )
                    .order_by(MeetingActionItem.due_date)
                )
            ).all()
        )
        return {
            "today": today,
            "upcoming": upcoming,
            "recent": recent,
            "pending_rsvps": pending,
            "my_action_items": [serialize(item) for item in actions],
        }

    async def _calendar(
        self, organization_id: uuid.UUID, body: MeetingCreate, actor_id: uuid.UUID
    ) -> Calendar:
        calendar = await self.session.get(Calendar, body.calendar_id) if body.calendar_id else None
        if calendar and calendar.organization_id != organization_id:
            raise NotFoundError("Calendar not found")
        if calendar:
            return calendar
        existing = await self.session.scalar(
            select(Calendar)
            .where(
                Calendar.organization_id == organization_id,
                Calendar.workspace_id == body.workspace_id,
                Calendar.owner_id == actor_id,
                Calendar.deleted_at.is_(None),
            )
            .order_by(Calendar.is_default.desc())
        )
        if existing:
            return existing
        return await CalendarService(self.session).create(
            organization_id,
            CalendarCreate(
                workspace_id=body.workspace_id,
                owner_id=actor_id,
                name="My Calendar",
                type=CalendarType.PERSONAL,
                timezone=body.timezone,
                is_default=True,
            ),
            actor_id,
        )

    async def _create_participant_event(
        self,
        meeting: Meeting,
        user_id: uuid.UUID,
        recurrence_input: RecurrenceRuleInput | None,
    ) -> CalendarEvent:
        calendar = await self.session.scalar(
            select(Calendar).where(
                Calendar.organization_id == meeting.organization_id,
                Calendar.workspace_id == meeting.workspace_id,
                Calendar.owner_id == user_id,
                Calendar.type == CalendarType.PERSONAL,
                Calendar.deleted_at.is_(None),
            )
        )
        if calendar is None:
            calendar = Calendar(
                organization_id=meeting.organization_id,
                workspace_id=meeting.workspace_id,
                owner_id=user_id,
                name="My Calendar",
                type=CalendarType.PERSONAL,
                timezone=meeting.timezone,
                visibility=Visibility.PRIVATE,
                is_default=True,
            )
            self.session.add(calendar)
            await self.session.flush()
        event = CalendarEvent(
            calendar_id=calendar.id,
            meeting_id=meeting.id,
            title=meeting.title,
            description=meeting.description,
            start_datetime=meeting.start_datetime,
            end_datetime=meeting.end_datetime,
            timezone=meeting.timezone,
            visibility=Visibility.PRIVATE,
            status=EventStatus.CONFIRMED,
            created_by=meeting.organizer_id,
            updated_by=meeting.organizer_id,
        )
        if recurrence_input is not None:
            recurrence = RecurrenceRule(
                **recurrence_input.model_dump(),
                exception_dates=[],
            )
            self.session.add(recurrence)
            await self.session.flush()
            event.recurrence_rule_id = recurrence.id
        self.session.add(event)
        await self.session.flush()
        return event

    async def _validate_users(self, organization_id: uuid.UUID, user_ids: set[uuid.UUID]) -> None:
        if not user_ids:
            return
        found = set(
            (
                await self.session.scalars(
                    select(User.id).where(
                        User.organization_id == organization_id, User.id.in_(user_ids)
                    )
                )
            ).all()
        )
        if found != user_ids:
            raise ValidationError("Every attendee must be an active organization member")

    async def _record(
        self,
        name: str,
        meeting: Meeting,
        actor_id: uuid.UUID,
        payload: dict[str, object] | None = None,
    ) -> None:
        await self.events.publish(
            DomainEvent(
                name=name,
                organization_id=meeting.organization_id,
                workspace_id=meeting.workspace_id,
                actor_id=actor_id,
                aggregate_type="meeting",
                aggregate_id=meeting.id,
                payload=payload or {},
            )
        )
        self.session.add(
            AuditLog(
                organization_id=meeting.organization_id,
                user_id=actor_id,
                action=name,
                resource="meeting",
                resource_id=meeting.id,
                audit_metadata=payload or {},
            )
        )
