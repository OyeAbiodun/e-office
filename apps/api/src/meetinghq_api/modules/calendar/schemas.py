"""Calendar API validation and representation contracts."""

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from meetinghq_api.modules.calendar.models import (
    CalendarType,
    EventStatus,
    RecurrenceFrequency,
    ResourceStatus,
    Visibility,
)


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CalendarCreate(BaseModel):
    workspace_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    color: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")
    type: CalendarType
    timezone: str = "UTC"
    visibility: Visibility = Visibility.MEMBERS
    is_default: bool = False


class CalendarUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    timezone: str | None = None
    visibility: Visibility | None = None
    is_default: bool | None = None


class CalendarResponse(OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    team_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    name: str
    description: str | None
    color: str
    type: CalendarType
    timezone: str
    visibility: Visibility
    is_default: bool
    created_at: datetime
    updated_at: datetime


class RecurrenceRuleInput(BaseModel):
    frequency: RecurrenceFrequency
    interval: int = Field(default=1, ge=1, le=365)
    days_of_week: list[int] = Field(default_factory=list)
    end_date: date | None = None
    occurrence_count: int | None = Field(default=None, ge=1, le=1000)
    skip_holidays: bool = False


class RecurrenceRuleResponse(OrmModel):
    id: uuid.UUID
    frequency: RecurrenceFrequency
    interval: int
    days_of_week: list[int]
    end_date: date | None
    occurrence_count: int | None
    exception_dates: list[str]
    skip_holidays: bool


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    start_datetime: datetime
    end_datetime: datetime
    timezone: str
    status: EventStatus = EventStatus.CONFIRMED
    visibility: Visibility = Visibility.MEMBERS
    all_day: bool = False
    recurrence: RecurrenceRuleInput | None = None
    category_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "EventCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    timezone: str | None = None
    status: EventStatus | None = None
    visibility: Visibility | None = None
    all_day: bool | None = None
    category_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "EventUpdate":
        if (
            self.start_datetime is not None
            and self.end_datetime is not None
            and self.end_datetime <= self.start_datetime
        ):
            raise ValueError("end_datetime must be after start_datetime")
        return self


class EventResponse(OrmModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    meeting_id: uuid.UUID | None
    title: str
    description: str | None
    start_datetime: datetime
    end_datetime: datetime
    timezone: str
    status: EventStatus
    visibility: Visibility
    all_day: bool
    recurrence_rule_id: uuid.UUID | None
    recurrence_parent_id: uuid.UUID | None
    original_start_datetime: datetime | None
    category_id: uuid.UUID | None


class RecurrenceExceptionCreate(EventUpdate):
    occurrence_start: datetime


class CalendarShareCreate(BaseModel):
    user_id: uuid.UUID
    permission: str = Field(default="read", pattern=r"^(read|write|manage)$")


class CalendarShareResponse(OrmModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    user_id: uuid.UUID
    permission: str
    shared_by: uuid.UUID
    created_at: datetime


class EventCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class EventCategoryResponse(OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    color: str


class AvailabilityCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    availability_type: str = "available"
    priority: int = 0

    @model_validator(mode="after")
    def validate_range(self) -> "AvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityResponse(OrmModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    weekday: int
    start_time: time
    end_time: time
    availability_type: str
    priority: int


class HolidayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    date: date
    recurring: bool = False


class HolidayResponse(OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    date: date
    recurring: bool


class BusyBlockCreate(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_range(self) -> "BusyBlockCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class BusyBlockResponse(OrmModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None


class ResourceCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    capacity: int = Field(default=1, ge=1)
    location: str | None = Field(default=None, max_length=240)
    status: ResourceStatus = ResourceStatus.AVAILABLE
    timezone: str = "UTC"


class ResourceResponse(OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    calendar_id: uuid.UUID
    name: str
    category: str
    capacity: int
    location: str | None
    status: ResourceStatus


class ReservationCreate(BaseModel):
    resource_id: uuid.UUID
    calendar_event_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime


class ReservationResponse(OrmModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    calendar_event_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    cancelled_at: datetime | None


class ScheduleValidationRequest(BaseModel):
    calendar_ids: list[uuid.UUID] = Field(min_length=1)
    resource_ids: list[uuid.UUID] = Field(default_factory=list)
    start_datetime: datetime
    end_datetime: datetime
    timezone: str = "UTC"
    buffer_minutes: int = Field(default=0, ge=0, le=240)


class ScheduleValidationResponse(BaseModel):
    valid: bool
    reasons: list[str]
    conflict_count: int


class SlotSuggestionRequest(ScheduleValidationRequest):
    search_end: datetime
    duration_minutes: int = Field(default=30, ge=15, le=720)
    limit: int = Field(default=10, ge=1, le=50)


class TimeSlot(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
