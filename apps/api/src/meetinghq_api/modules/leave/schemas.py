"""Leave Management API contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class LeaveTypeInput(InputModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool = True
    is_paid: bool = True
    default_entitlement: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=2
    )
    accrual_enabled: bool = False
    accrual_frequency: Literal["monthly", "quarterly", "yearly"] | None = None
    carryover_enabled: bool = False
    carryover_limit: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    carryover_expiry_months: int | None = Field(default=None, ge=1, le=120)
    minimum_notice_days: int = Field(default=0, ge=0, le=365)
    maximum_consecutive_days: int | None = Field(default=None, ge=1, le=366)
    attachment_required: bool = False
    half_day_supported: bool = False
    eligible_employment_types: list[str] = Field(default_factory=list, max_length=20)
    probation_eligible: bool = True
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_policy(self) -> LeaveTypeInput:
        if self.accrual_enabled != (self.accrual_frequency is not None):
            raise ValueError("Accrual frequency must be set only when accrual is enabled")
        if self.carryover_enabled and self.carryover_limit is None:
            raise ValueError("Carryover limit is required when carryover is enabled")
        if not self.carryover_enabled and (
            self.carryover_limit is not None or self.carryover_expiry_months is not None
        ):
            raise ValueError("Carryover values require carryover to be enabled")
        return self


class LeavePeriodInput(InputModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    status: Literal["open", "closed"] = "open"

    @model_validator(mode="after")
    def valid_dates(self) -> LeavePeriodInput:
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before start date")
        return self


class EntitlementInput(InputModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID
    allocated_days: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    reason: str | None = Field(default=None, max_length=1000)


class AdjustmentInput(InputModel):
    operation: Literal["add", "deduct", "correction"] = "correction"
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    effective_date: date
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def nonzero(self) -> AdjustmentInput:
        if not self.amount:
            raise ValueError("Adjustment amount cannot be zero")
        if self.operation in {"add", "deduct"} and self.amount < 0:
            raise ValueError("Add and deduct operations require a positive amount")
        return self


class ControlledAdjustmentInput(AdjustmentInput):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID


class PeriodStatusInput(InputModel):
    status: Literal["open", "closed"]


class WorkingWeekInput(InputModel):
    weekdays: list[int] = Field(min_length=1, max_length=7)
    exclude_holidays: bool = True

    @model_validator(mode="after")
    def valid_weekdays(self) -> WorkingWeekInput:
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            day < 0 or day > 6 for day in self.weekdays
        ):
            raise ValueError("Weekdays must be unique values from 0 (Monday) to 6 (Sunday)")
        return self


class LeaveRequestInput(InputModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day: bool = False
    reason: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def valid_dates(self) -> LeaveRequestInput:
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before start date")
        if self.half_day and self.start_date != self.end_date:
            raise ValueError("Half-day leave must be requested for one date")
        return self


class ReviewInput(InputModel):
    comment: str | None = Field(default=None, max_length=4000)


class RejectInput(InputModel):
    comment: str = Field(min_length=1, max_length=4000)


class WorkingDayPreview(InputModel):
    start_date: date
    end_date: date
    half_day: bool = False


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LeaveTypeResponse(OrmResponse):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    is_active: bool
    is_paid: bool
    default_entitlement: Decimal
    accrual_enabled: bool
    accrual_frequency: str | None
    carryover_enabled: bool
    carryover_limit: Decimal | None
    carryover_expiry_months: int | None
    minimum_notice_days: int
    maximum_consecutive_days: int | None
    attachment_required: bool
    half_day_supported: bool
    eligible_employment_types: str | None
    probation_eligible: bool
    color: str | None


class LeavePeriodResponse(OrmResponse):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str


class EntitlementResponse(OrmResponse):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID
    allocated_days: Decimal


class BalanceResponse(BaseModel):
    entitlement_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID
    entitled: Decimal
    accrued: Decimal
    carried_forward: Decimal
    adjustments: Decimal
    used: Decimal
    pending: Decimal
    expired: Decimal
    available: Decimal
    available_after_pending: Decimal


class LeaveRequestResponse(OrmResponse):
    id: uuid.UUID
    employee_id: uuid.UUID
    department_id: uuid.UUID | None
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID
    start_date: date
    end_date: date
    duration_days: Decimal
    half_day: bool
    reason: str | None
    status: str
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_comment: str | None
    calendar_event_id: uuid.UUID | None
    employee_number: str | None = None
    employee_name: str | None = None
    department_name: str | None = None
    leave_type_name: str | None = None
    leave_type_code: str | None = None
    leave_period_name: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkingDayResult(BaseModel):
    calendar_span: int
    excluded_non_working_days: int
    excluded_holidays: int
    chargeable_days: Decimal


class LeaveAttachmentResponse(OrmResponse):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    uploaded_by_id: uuid.UUID
    created_at: datetime


class AdjustmentResponse(BaseModel):
    previous_balance: BalanceResponse
    adjustment: LedgerEntryResponse
    resulting_balance: BalanceResponse


class WorkingWeekResponse(BaseModel):
    weekdays: list[int]
    exclude_holidays: bool


class LeaveHistoryResponse(OrmResponse):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    event_type: str
    comment: str | None
    created_at: datetime


class LeaveRequestDetail(LeaveRequestResponse):
    employee_number: str | None
    employee_name: str
    department_name: str | None
    manager_id: uuid.UUID | None
    manager_name: str | None
    leave_type_name: str
    leave_type_code: str
    leave_period_name: str
    reviewer_name: str | None
    balance_effect: Decimal
    attachments: list[LeaveAttachmentResponse]
    history: list[LeaveHistoryResponse]


class BalanceListItem(BalanceResponse):
    employee_number: str | None
    employee_name: str
    department_id: uuid.UUID | None
    department_name: str | None
    leave_type_name: str
    leave_type_code: str
    period_name: str


class BalancePage(BaseModel):
    items: list[BalanceListItem]
    total: int
    page: int
    page_size: int


class LedgerEntryResponse(OrmResponse):
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_period_id: uuid.UUID
    entry_type: str
    amount: Decimal
    effective_date: date
    reason: str | None
    reference_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    actor_name: str | None = None
    created_at: datetime


class LedgerPage(BaseModel):
    items: list[LedgerEntryResponse]
    total: int
    page: int
    page_size: int


class LeaveRequestPage(BaseModel):
    items: list[LeaveRequestResponse]
    total: int
    page: int
    page_size: int


class LeaveAvailabilityItem(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    start_date: date
    end_date: date
    status: Literal["away"] = "away"


class LeaveSummaryResponse(BaseModel):
    balances: list[BalanceResponse]
    pending_requests: list[LeaveRequestResponse]
    upcoming_approved: list[LeaveRequestResponse]
    recent_history: list[LeaveRequestResponse]


class ManagerLeaveSummary(BaseModel):
    pending_count: int
    pending: list[LeaveRequestResponse]
    away_today: list[LeaveAvailabilityItem]
    upcoming: list[LeaveAvailabilityItem]
    recently_reviewed: list[LeaveRequestResponse]


class LeaveStatusSummary(BaseModel):
    status: str
    request_count: int
    total_days: Decimal


class LeaveReportRow(BaseModel):
    key: str
    label: str
    request_count: int
    total_days: Decimal
