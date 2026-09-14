"""Reporting contracts."""

import uuid
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def default_report_types() -> list[Literal["daily", "weekly", "monthly", "custom"]]:
    return ["daily", "weekly", "monthly", "custom"]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PolicyUpdate(BaseModel):
    daily_enabled: bool = True
    weekly_enabled: bool = True
    monthly_enabled: bool = True
    review_before_send: bool = True
    automatic_submit: bool = False
    week_start: int = Field(0, ge=0, le=6)
    week_end: int = Field(6, ge=0, le=6)
    generation_time: time = time(18, 0)
    submission_deadline_hours: int = Field(24, ge=1, le=336)
    manager_review_required: bool = True
    reminder_hours_before: int = Field(4, ge=0, le=168)
    timezone: str = Field("UTC", min_length=1, max_length=80)
    enabled_report_types: list[Literal["daily", "weekly", "monthly", "custom"]] = Field(
        default_factory=default_report_types
    )

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Timezone must be a valid IANA timezone") from error
        return value


class PolicyResponse(PolicyUpdate, OrmModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    updated_at: datetime


class GenerateReportInput(BaseModel):
    report_type: Literal["employee", "team", "department", "project", "management"]
    period_type: Literal["daily", "weekly", "monthly", "custom"] = "custom"
    period_start: date
    period_end: date
    subject_id: uuid.UUID | None = None
    scheduled: bool = False

    @model_validator(mode="after")
    def valid_period(self) -> "GenerateReportInput":
        if self.period_end < self.period_start:
            raise ValueError("Period end must be on or after period start")
        if (self.period_end - self.period_start).days > 366:
            raise ValueError("Report periods cannot exceed 366 days")
        if self.report_type != "management" and self.subject_id is None:
            raise ValueError("A report subject is required")
        return self


class NarrativeUpdate(BaseModel):
    accomplishments: str | None = Field(None, max_length=10000)
    challenges: str | None = Field(None, max_length=10000)
    explanation: str | None = Field(None, max_length=10000)
    follow_ups: str | None = Field(None, max_length=10000)
    next_priorities: str | None = Field(None, max_length=10000)
    notes: str | None = Field(None, max_length=10000)


class ReviewInput(BaseModel):
    action: Literal["accept", "return"]
    comment: str | None = Field(None, max_length=5000)

    @model_validator(mode="after")
    def return_reason(self) -> "ReviewInput":
        if self.action == "return" and not (self.comment or "").strip():
            raise ValueError("A return reason is required")
        return self


class ReportResponse(OrmModel):
    id: uuid.UUID
    report_type: str
    subject_type: str
    subject_id: uuid.UUID | None
    subject_name: str
    owner_id: uuid.UUID | None
    manager_id: uuid.UUID | None
    period_type: str
    period_start: date
    period_end: date
    timezone: str
    status: str
    submission_mode: str | None
    version: int
    authoritative_snapshot: dict[str, object]
    narrative: dict[str, object]
    source_refs: list[dict[str, object]]
    policy_snapshot: dict[str, object]
    reviewer_id: uuid.UUID | None
    review_comment: str | None
    return_reason: str | None
    generated_at: datetime
    submitted_at: datetime | None
    submission_reminder_sent_at: datetime | None
    reviewed_at: datetime | None
    finalized_at: datetime | None


class ReportPage(BaseModel):
    items: list[ReportResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReportVersionResponse(OrmModel):
    id: uuid.UUID
    version: int
    snapshot: dict[str, object]
    narrative: dict[str, object]
    created_at: datetime


class ReviewHistoryResponse(OrmModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    note: str | None
    created_at: datetime


class ReportDetail(BaseModel):
    report: ReportResponse
    versions: list[ReportVersionResponse]
    history: list[ReviewHistoryResponse]


class ReportingDashboard(BaseModel):
    pending_my_review: int
    awaiting_manager_review: int
    returned: int
    finalized_this_period: int
    reporting_compliance_percent: int
    active_projects: int
    projects_at_risk: int
    open_tasks: int
    overdue_tasks: int
    unresolved_blockers: int
    department_activity: list[dict[str, object]]
