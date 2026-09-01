"""Meeting API contracts."""

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meetinghq_api.modules.calendar.schemas import RecurrenceRuleInput
from meetinghq_api.modules.meetings.models import AttendanceStatus, MeetingStatus


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeetingCreate(BaseModel):
    workspace_id: uuid.UUID
    calendar_id: uuid.UUID | None = None
    meeting_template_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    agenda: str | None = Field(default=None, max_length=16000)
    meeting_type: str = Field(default="standard", max_length=64)
    location_type: str = Field(default="virtual", max_length=32)
    meeting_url: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=500)
    room_id: uuid.UUID | None = None
    start_datetime: datetime
    end_datetime: datetime
    timezone: str = "UTC"
    visibility: str = "members"
    attendee_ids: list[uuid.UUID] = Field(default_factory=list)
    cohost_ids: list[uuid.UUID] = Field(default_factory=list)
    recurrence: RecurrenceRuleInput | None = None

    @model_validator(mode="after")
    def valid_range(self) -> "MeetingCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    agenda: str | None = Field(default=None, max_length=16000)
    meeting_type: str | None = None
    location_type: str | None = None
    meeting_url: str | None = None
    location: str | None = Field(default=None, max_length=500)
    visibility: str | None = None


class MeetingResponse(OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    calendar_event_id: uuid.UUID | None
    meeting_template_id: uuid.UUID | None
    title: str
    description: str | None
    agenda_text: str | None = None
    meeting_type: str
    location_type: str
    meeting_url: str | None
    location: str | None
    recurrence: dict[str, object] | None
    room_id: uuid.UUID | None
    organizer_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    timezone: str
    status: MeetingStatus
    visibility: str
    sequence: int
    created_at: datetime
    updated_at: datetime

    @field_validator("start_datetime", "end_datetime", mode="before")
    @classmethod
    def serialize_as_utc(cls, value: datetime) -> datetime:
        """Keep meeting instants unambiguous across SQLite and PostgreSQL."""
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TransitionRequest(BaseModel):
    status: MeetingStatus


class RescheduleRequest(BaseModel):
    calendar_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    start_datetime: datetime
    end_datetime: datetime
    timezone: str = "UTC"


class AttendeeCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "attendee"


class RSVPRequest(BaseModel):
    status: AttendanceStatus


class AgendaInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    owner_id: uuid.UUID | None = None
    duration_minutes: int = Field(default=10, ge=1, le=480)
    sort_order: int = Field(default=0, ge=0)


class AgendaOrder(BaseModel):
    agenda_ids: list[uuid.UUID]


class DecisionInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    status: str = "recorded"


class ActionItemInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    due_date: date | None = None
    priority: str = "medium"
    status: str = "open"


class NoteInput(BaseModel):
    content: str = Field(min_length=1, max_length=50000)


class ArtifactInput(BaseModel):
    artifact_type: str = Field(default="link", max_length=32)
    title: str = Field(min_length=1, max_length=240)
    storage_key: str | None = Field(default=None, max_length=1000)
    content_type: str | None = Field(default=None, max_length=160)
    size: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class RecordingInput(BaseModel):
    provider: str = Field(default="meetinghq", max_length=64)
    status: str = Field(default="ready", max_length=32)
    storage_key: str | None = Field(default=None, max_length=1000)
    duration_seconds: int | None = Field(default=None, ge=0)
    transcript_status: str = Field(default="not_requested", max_length=32)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class AttendanceEventInput(BaseModel):
    user_id: uuid.UUID
    event_type: str = Field(pattern=r"^(joined|left|no_show)$")
    occurred_at: datetime | None = None


class PresenterControlInput(BaseModel):
    user_id: uuid.UUID
    control: str = Field(pattern=r"^(present|share_screen|moderate|record)$")
    enabled: bool = True


class FollowUpInput(BaseModel):
    follow_up_type: str = Field(
        pattern=r"^(summary|action_reminder|attendance_report|decision_digest)$"
    )
    scheduled_for: datetime
    payload: dict[str, object] = Field(default_factory=dict)


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    default_duration: int = Field(default=30, ge=15, le=720)
    default_visibility: str = "members"
    default_agenda: list[dict[str, object]] = Field(default_factory=list)


class CollaborationItem(OrmModel):
    id: uuid.UUID


class MeetingDetail(MeetingResponse):
    attendees: list[dict[str, object]] = Field(default_factory=list)
    agenda: list[dict[str, object]] = Field(default_factory=list)
    decisions: list[dict[str, object]] = Field(default_factory=list)
    action_items: list[dict[str, object]] = Field(default_factory=list)
    notes: list[dict[str, object]] = Field(default_factory=list)
    artifacts: list[dict[str, object]] = Field(default_factory=list)
    recordings: list[dict[str, object]] = Field(default_factory=list)
    attendance_events: list[dict[str, object]] = Field(default_factory=list)
    presenter_controls: list[dict[str, object]] = Field(default_factory=list)
    follow_ups: list[dict[str, object]] = Field(default_factory=list)


class MeetingAnalytics(BaseModel):
    attendee_count: int
    joined_count: int
    attendance_rate: float
    average_minutes_attended: float
    agenda_items: int
    decisions: int
    action_items: int
    completed_actions: int
    follow_ups_pending: int


class MeetingDashboard(BaseModel):
    today: list[MeetingResponse]
    upcoming: list[MeetingResponse]
    recent: list[MeetingResponse]
    pending_rsvps: int
    my_action_items: list[dict[str, object]]
