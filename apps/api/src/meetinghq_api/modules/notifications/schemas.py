"""Notification API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID | None
    notification_type: str
    category: str
    priority: str
    title: str
    body: str
    action_url: str | None
    delivered_at: datetime
    read_at: datetime | None
    archived_at: datetime | None
    notification_metadata: dict[str, object]


class NotificationSummary(BaseModel):
    unread: int
    mentions: int = 0
    meetings: int = 0
    approvals: int = 0
    tasks: int = 0
    total: int
    page: int
    page_size: int
    total_pages: int
    next_cursor: str | None = None
    notifications: list[NotificationResponse]


class NotificationBulkAction(BaseModel):
    notification_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^(read|archive)$")


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    in_app_enabled: bool
    email_enabled: bool
    browser_enabled: bool
    quiet_hours_enabled: bool
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    timezone: str
    category_rules: dict[str, object]
    delivery_rules: dict[str, object]
    updated_at: datetime


class NotificationPreferenceUpdate(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = True
    browser_enabled: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(default="UTC", max_length=64)
    category_rules: dict[str, object] = Field(default_factory=dict)
    delivery_rules: dict[str, object] = Field(default_factory=dict)
