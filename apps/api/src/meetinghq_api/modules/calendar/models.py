"""Calendar, availability, recurrence, and resource persistence models."""

# ruff: noqa: E501

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base
from meetinghq_api.shared.soft_delete import SoftDeleteMixin

json_type = JSON().with_variant(JSONB(), "postgresql")


class CalendarType(enum.StrEnum):
    PERSONAL = "personal"
    TEAM = "team"
    WORKSPACE = "workspace"
    ORGANIZATION = "organization"
    RESOURCE = "resource"


class Visibility(enum.StrEnum):
    PRIVATE = "private"
    MEMBERS = "members"
    PUBLIC = "public"


class EventStatus(enum.StrEnum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class RecurrenceFrequency(enum.StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ResourceStatus(enum.StrEnum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    UNAVAILABLE = "unavailable"


class Calendar(SoftDeleteMixin, Base):
    __tablename__ = "calendars"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#2563eb")
    type: Mapped[CalendarType] = mapped_column(Enum(CalendarType, native_enum=False))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, native_enum=False), default=Visibility.MEMBERS
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecurrenceRule(Base):
    __tablename__ = "recurrence_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        Enum(RecurrenceFrequency, native_enum=False)
    )
    interval: Mapped[int] = mapped_column(Integer, default=1)
    days_of_week: Mapped[list[int]] = mapped_column(json_type, default=list)
    end_date: Mapped[date | None] = mapped_column(Date)
    occurrence_count: Mapped[int | None] = mapped_column(Integer)
    exception_dates: Mapped[list[str]] = mapped_column(json_type, default=list)
    skip_holidays: Mapped[bool] = mapped_column(Boolean, default=False)


class CalendarEvent(SoftDeleteMixin, Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), index=True)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, native_enum=False), default=EventStatus.CONFIRMED
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, native_enum=False), default=Visibility.MEMBERS
    )
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurrence_rules.id"))
    recurrence_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calendar_events.id"), index=True
    )
    original_start_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("event_categories.id"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"
    __table_args__ = (UniqueConstraint("calendar_id", "weekday", "start_time", "end_time"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    availability_type: Mapped[str] = mapped_column(String(40), default="available")
    priority: Mapped[int] = mapped_column(Integer, default=0)


class Holiday(Base):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("organization_id", "name", "date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    date: Mapped[date] = mapped_column(Date, index=True)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)


class BusyBlock(Base):
    __tablename__ = "busy_blocks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), index=True)
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[str | None] = mapped_column(String(240))


class Resource(SoftDeleteMixin, Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    location: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, native_enum=False), default=ResourceStatus.AVAILABLE
    )


class ResourceReservation(Base):
    __tablename__ = "resource_reservations"
    __table_args__ = (UniqueConstraint("resource_id", "calendar_event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), index=True)
    calendar_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendar_events.id"), index=True
    )
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CalendarShare(Base):
    __tablename__ = "calendar_shares"
    __table_args__ = (UniqueConstraint("calendar_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendars.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    permission: Mapped[str] = mapped_column(String(24), default="read")
    shared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventCategory(Base):
    __tablename__ = "event_categories"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
