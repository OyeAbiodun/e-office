"""Project Management API contracts."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProjectStatus = Literal[
    "draft", "planned", "active", "on_hold", "completed", "cancelled", "archived"
]
ProjectPriority = Literal["low", "normal", "high", "urgent"]
ProjectHealth = Literal["on_track", "at_risk", "off_track", "completed"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    project_code: str | None = Field(
        default=None, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9-]+$"
    )
    description: str | None = Field(default=None, max_length=20000)
    project_manager_id: uuid.UUID
    sponsor_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    start_date: date | None = None
    target_end_date: date | None = None
    priority: ProjectPriority = "normal"
    visibility: Literal["members", "department", "organization"] = "members"
    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ProjectCreate":
        if self.start_date and self.target_end_date and self.target_end_date < self.start_date:
            raise ValueError("target_end_date cannot precede start_date")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    project_manager_id: uuid.UUID | None = None
    sponsor_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    start_date: date | None = None
    target_end_date: date | None = None
    status: ProjectStatus | None = None
    priority: ProjectPriority | None = None
    health: ProjectHealth | None = None
    manual_progress: int | None = Field(default=None, ge=0, le=100)
    progress_mode: Literal["task_based", "milestone_based", "manual"] | None = None
    visibility: Literal["members", "department", "organization"] | None = None
    completion_override: bool = False


class MemberInput(BaseModel):
    user_id: uuid.UUID
    role: Literal["project_manager", "project_lead", "member", "viewer"] = "member"


class MemberUpdate(BaseModel):
    role: Literal["project_manager", "project_lead", "member", "viewer"]


class MilestoneInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    target_date: date | None = None
    owner_id: uuid.UUID | None = None
    sequence: int | None = Field(default=None, ge=0)


class MilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    target_date: date | None = None
    owner_id: uuid.UUID | None = None
    status: Literal["not_started", "in_progress", "completed", "delayed", "cancelled"] | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    sequence: int | None = Field(default=None, ge=0)


class ProjectUpdateInput(BaseModel):
    reporting_date: date
    summary: str = Field(min_length=1, max_length=20000)
    accomplishments: str | None = Field(default=None, max_length=20000)
    current_status: str | None = Field(default=None, max_length=10000)
    blockers: str | None = Field(default=None, max_length=10000)
    risks: str | None = Field(default=None, max_length=10000)
    next_steps: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=10000)


class RiskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    probability: Literal["low", "medium", "high", "critical"] = "medium"
    impact: Literal["low", "medium", "high", "critical"] = "medium"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    owner_id: uuid.UUID | None = None
    mitigation: str | None = Field(default=None, max_length=10000)
    status: Literal["open", "monitoring", "mitigated", "closed"] = "open"
    review_date: date | None = None


class RiskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    probability: Literal["low", "medium", "high", "critical"] | None = None
    impact: Literal["low", "medium", "high", "critical"] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    owner_id: uuid.UUID | None = None
    mitigation: str | None = Field(default=None, max_length=10000)
    status: Literal["open", "monitoring", "mitigated", "closed"] | None = None
    review_date: date | None = None


class IssueInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: Literal["open", "in_progress", "resolved", "closed"] = "open"
    resolution: str | None = Field(default=None, max_length=10000)


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    resolution: str | None = Field(default=None, max_length=10000)


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectSummary(OrmResponse):
    id: uuid.UUID
    project_code: str
    name: str
    description: str | None
    project_manager_id: uuid.UUID
    department_id: uuid.UUID | None
    start_date: date | None
    target_end_date: date | None
    actual_end_date: date | None
    status: str
    priority: str
    health: str
    progress: int = 0
    visibility: str
    archived_at: datetime | None
    created_at: datetime
    manager_name: str | None = None
    department_name: str | None = None
    member_count: int = 0
    task_count: int = 0
    completed_task_count: int = 0
    overdue_task_count: int = 0
    milestone_count: int = 0
    open_risk_count: int = 0
    open_issue_count: int = 0


class ProjectPage(BaseModel):
    items: list[ProjectSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class MemberResponse(OrmResponse):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    display_name: str | None = None
    job_title: str | None = None
    avatar_url: str | None = None


class MilestoneResponse(OrmResponse):
    id: uuid.UUID
    name: str
    description: str | None
    start_date: date | None
    target_date: date | None
    completion_date: date | None
    status: str
    owner_id: uuid.UUID | None
    progress: int
    sequence: int
    created_at: datetime
    owner_name: str | None = None


class UpdateResponse(OrmResponse):
    id: uuid.UUID
    reporting_date: date
    summary: str
    accomplishments: str | None
    current_status: str | None
    blockers: str | None
    risks: str | None
    next_steps: str | None
    notes: str | None
    created_by_id: uuid.UUID
    created_at: datetime
    author_name: str | None = None


class RiskResponse(OrmResponse):
    id: uuid.UUID
    title: str
    description: str | None
    probability: str
    impact: str
    severity: str
    owner_id: uuid.UUID | None
    mitigation: str | None
    status: str
    review_date: date | None
    created_at: datetime
    owner_name: str | None = None


class IssueResponse(OrmResponse):
    id: uuid.UUID
    title: str
    description: str | None
    severity: str
    owner_id: uuid.UUID | None
    due_date: date | None
    status: str
    resolution: str | None
    created_at: datetime
    owner_name: str | None = None


class AttachmentResponse(OrmResponse):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    uploaded_by_id: uuid.UUID
    created_at: datetime


class ProjectDetail(BaseModel):
    project: ProjectSummary
    members: list[MemberResponse]
    milestones: list[MilestoneResponse]
    updates: list[UpdateResponse]
    risks: list[RiskResponse]
    issues: list[IssueResponse]
    attachments: list[AttachmentResponse]
    meetings: list[dict[str, object]]
    activity: list[dict[str, object]]


class ProjectReport(BaseModel):
    project: ProjectSummary
    start_date: date
    end_date: date
    executive_summary: str
    milestones: list[MilestoneResponse]
    tasks_total: int
    tasks_completed: int
    tasks_overdue: int
    activities: list[dict[str, object]]
    updates: list[UpdateResponse]
    risks: list[RiskResponse]
    issues: list[IssueResponse]
    meetings: list[dict[str, object]]
    upcoming_deadlines: list[dict[str, object]]
    generated_at: datetime
