"""Public API contracts for work management."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal[
    "not_started", "in_progress", "blocked", "awaiting_review", "completed", "cancelled"
]
TaskPriority = Literal["low", "normal", "high", "urgent"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    due_date: date | None = None
    priority: TaskPriority = "normal"
    description: str | None = Field(default=None, max_length=20000)
    assignee_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    meeting_action_item_id: uuid.UUID | None = None
    start_date: date | None = None
    reminder_at: datetime | None = None
    follow_up_at: datetime | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    reminder_at: datetime | None = None
    follow_up_at: datetime | None = None
    tags: list[str] | None = Field(default=None, max_length=20)


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class TaskChecklistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    position: int | None = Field(default=None, ge=0)


class TaskChecklistItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    completed: bool | None = None
    position: int | None = Field(default=None, ge=0)


class DailyActivityCreate(BaseModel):
    activity_date: date
    summary: str = Field(min_length=1, max_length=20000)
    task_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    outcome: str | None = Field(default=None, max_length=10000)
    blockers: str | None = Field(default=None, max_length=10000)
    next_step: str | None = Field(default=None, max_length=10000)
    visibility: Literal["private", "manager", "department"] = "manager"


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence: int
    title: str
    description: str | None
    status: str
    priority: str
    progress: int | None
    assignee_id: uuid.UUID
    created_by_id: uuid.UUID
    assigned_by_id: uuid.UUID | None
    department_id: uuid.UUID | None
    team_id: uuid.UUID | None
    meeting_id: uuid.UUID | None
    meeting_action_item_id: uuid.UUID | None
    start_date: date | None
    due_date: date | None
    completed_at: datetime | None
    reminder_at: datetime | None
    follow_up_at: datetime | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
    overdue_days: int = 0
    assignee_name: str | None = None
    department_name: str | None = None
    meeting_title: str | None = None


class TaskPage(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskAssigneeResponse(BaseModel):
    """Authorization-filtered employee data for the task assignment picker."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    job_title: str | None
    department_id: uuid.UUID | None
    department_name: str | None = None


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime
    updated_at: datetime
    author_name: str | None = None


class TaskHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type: str
    payload: dict[str, object]
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None = None


class TaskDetailResponse(BaseModel):
    task: TaskResponse
    comments: list[TaskCommentResponse]
    history: list[TaskHistoryResponse]
    attachments: list["TaskAttachmentResponse"] = Field(default_factory=list)
    checklist: list["TaskChecklistItemResponse"] = Field(default_factory=list)


class TaskAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    url: str
    uploaded_by_id: uuid.UUID
    created_at: datetime


class TaskChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    position: int
    completed_at: datetime | None
    completed_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DailyActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    department_id: uuid.UUID | None
    task_id: uuid.UUID | None
    meeting_id: uuid.UUID | None
    activity_date: date
    summary: str
    duration_minutes: int | None
    outcome: str | None
    blockers: str | None
    next_step: str | None
    visibility: str
    created_at: datetime
    user_name: str | None = None


class DailySummary(BaseModel):
    date: date
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    activities: list[DailyActivityResponse]
    blockers: list[str]
    meetings_attended: int
    upcoming_due: int


class WeeklySummary(BaseModel):
    start_date: date
    end_date: date
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    activity_count: int
    activity_minutes: int
    meetings_attended: int
    upcoming_due: int
    workload: list[dict[str, object]] = Field(default_factory=list)
