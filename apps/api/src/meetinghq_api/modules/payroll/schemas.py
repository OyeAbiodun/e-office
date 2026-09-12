"""Typed Payroll API contracts with Decimal-only monetary values."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Decimal


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class SalaryComponentInput(InputModel):
    code: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    component_kind: Literal["earning", "deduction"]
    calculation_type: Literal["fixed", "percentage"] = "fixed"
    taxable: bool = True
    pensionable: bool = False
    recurring: bool = True
    is_active: bool = True
    effective_start: date
    effective_end: date | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> SalaryComponentInput:
        if self.effective_end and self.effective_end < self.effective_start:
            raise ValueError("effective_end cannot precede effective_start")
        return self


class SalaryStructureItemInput(InputModel):
    component_id: uuid.UUID
    amount: Money = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=6)


class SalaryStructureInput(InputModel):
    employee_id: uuid.UUID
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")
    basic_salary: Money = Field(ge=0, max_digits=18, decimal_places=2)
    effective_start: date
    effective_end: date | None = None
    status: Literal["draft", "active", "ended"] = "active"
    pension_participates: bool = True
    nhf_participates: bool = True
    paye_participates: bool = True
    notes: str | None = Field(default=None, max_length=10000)
    change_reason: str = Field(min_length=1, max_length=1000)
    items: list[SalaryStructureItemInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_dates(self) -> SalaryStructureInput:
        if self.effective_end and self.effective_end < self.effective_start:
            raise ValueError("effective_end cannot precede effective_start")
        return self


class SalaryStructureEndInput(InputModel):
    effective_end: date
    reason: str = Field(min_length=1, max_length=1000)


class SalaryPreviewResponse(BaseModel):
    currency: str
    basic_salary: Money
    allowances: Money
    gross_pay: Money
    taxable_pay: Money
    paye: Money
    pension_employee: Money
    pension_employer: Money
    nhf: Money
    other_deductions: Money
    total_deductions: Money
    net_pay: Money
    employer_cost: Money
    items: list[dict[str, object]]
    statutory_snapshot: dict[str, object]


class StatutoryConfigurationInput(InputModel):
    configuration_type: Literal["paye", "pension", "nhf", "payroll_policy"]
    name: str = Field(min_length=1, max_length=160)
    effective_start: date
    effective_end: date | None = None
    rules: dict[str, object]
    is_active: bool = True
    change_reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid_dates(self) -> StatutoryConfigurationInput:
        if self.effective_end and self.effective_end < self.effective_start:
            raise ValueError("effective_end cannot precede effective_start")
        return self


class PayrollPeriodInput(InputModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    payment_date: date
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_dates(self) -> PayrollPeriodInput:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if self.payment_date < self.end_date:
            raise ValueError("payment_date cannot precede the period end")
        return self


class PayrollAdjustmentInput(InputModel):
    employee_id: uuid.UUID
    adjustment_type: Literal["bonus", "overtime", "arrears", "deduction", "salary_advance"]
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=128)
    status: Literal["pending", "approved"] = "approved"


class PayrollLoanInput(InputModel):
    employee_id: uuid.UUID
    principal: Money = Field(gt=0, max_digits=18, decimal_places=2)
    start_date: date
    repayment_amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    repayment_frequency: Literal["monthly"] = "monthly"
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid_repayment(self) -> PayrollLoanInput:
        if self.repayment_amount > self.principal:
            raise ValueError("repayment_amount cannot exceed principal")
        return self


class PayrollDecisionInput(InputModel):
    reason: str | None = Field(default=None, max_length=2000)


class PayrollReturnInput(InputModel):
    reason: str = Field(min_length=1, max_length=2000)


class PayrollPaymentInput(InputModel):
    account_id: uuid.UUID
    payment_date: date
    payment_reference: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PayrollReversalInput(InputModel):
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PayrollResultFilters(InputModel):
    department_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    exception_only: bool = False
    payment_status: str | None = None
    search: str | None = Field(default=None, max_length=160)
    sort: Literal["employee", "gross", "net", "department", "status"] = "employee"
    direction: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=10, le=100)

    @field_validator("page_size")
    @classmethod
    def supported_page_size(cls, value: int) -> int:
        if value not in {10, 25, 50, 100}:
            raise ValueError("page_size must be one of 10, 25, 50, or 100")
        return value


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SalaryComponentResponse(OrmResponse):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    component_kind: str
    calculation_type: str
    taxable: bool
    pensionable: bool
    recurring: bool
    is_system: bool
    is_active: bool
    effective_start: date
    effective_end: date | None
    created_at: datetime


class SalaryStructureItemResponse(OrmResponse):
    id: uuid.UUID
    component_id: uuid.UUID
    amount: Money
    percentage: Decimal
    component_code: str | None = None
    component_name: str | None = None
    component_kind: str | None = None


class SalaryStructureResponse(OrmResponse):
    id: uuid.UUID
    employee_id: uuid.UUID
    currency: str
    basic_salary: Money
    effective_start: date
    effective_end: date | None
    status: str
    pension_participates: bool
    nhf_participates: bool
    paye_participates: bool
    notes: str | None
    change_reason: str
    created_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    employee_name: str | None = None
    changed_by_name: str | None = None
    gross_salary: Money = Decimal("0")
    items: list[SalaryStructureItemResponse] = Field(default_factory=list)


class StatutoryConfigurationResponse(OrmResponse):
    id: uuid.UUID
    configuration_type: str
    name: str
    effective_start: date
    effective_end: date | None
    rules: dict[str, object]
    is_active: bool
    change_reason: str
    created_by_id: uuid.UUID
    created_at: datetime


class PayrollPeriodResponse(OrmResponse):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    payment_date: date
    currency: str
    status: str
    locked: bool
    created_by_id: uuid.UUID
    created_at: datetime


class PayrollRunResponse(OrmResponse):
    id: uuid.UUID
    period_id: uuid.UUID
    status: str
    version: int
    prepared_by_id: uuid.UUID | None
    prepared_at: datetime | None
    submitted_by_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    returned_by_id: uuid.UUID | None
    returned_at: datetime | None
    return_reason: str | None
    paid_by_id: uuid.UUID | None
    paid_at: datetime | None
    closed_at: datetime | None
    created_at: datetime


class PayrollResultItemResponse(OrmResponse):
    id: uuid.UUID
    code: str
    name: str
    category: str
    amount: Money
    taxable: bool
    pensionable: bool
    basis: str | None
    position: int


class PayrollResultResponse(OrmResponse):
    id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_number: str | None
    department_name: str | None
    job_title: str | None
    currency: str
    status: str
    basic_salary: Money
    allowances: Money
    variable_earnings: Money
    gross_pay: Money
    taxable_pay: Money
    paye: Money
    pension_employee: Money
    pension_employer: Money
    nhf: Money
    loan_deductions: Money
    other_deductions: Money
    total_deductions: Money
    net_pay: Money
    employer_cost: Money
    proration_factor: Decimal
    calculation_snapshot: dict[str, object]
    exceptions: list[dict[str, object]]
    payslip_generated_at: datetime | None
    created_at: datetime
    items: list[PayrollResultItemResponse] = Field(default_factory=list)


class PayrollResultPage(BaseModel):
    items: list[PayrollResultResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PayrollSummary(BaseModel):
    employee_count: int
    exception_count: int
    currency: str
    gross_payroll: Money
    paye: Money
    pension_employee: Money
    pension_employer: Money
    nhf: Money
    loan_deductions: Money
    other_deductions: Money
    total_deductions: Money
    net_payroll: Money
    employer_cost: Money


class PayrollRunDetail(BaseModel):
    run: PayrollRunResponse
    period: PayrollPeriodResponse
    summary: PayrollSummary
    results: PayrollResultPage
    history: list[dict[str, object]]
    allowed_actions: list[str]


class PayrollLoanResponse(OrmResponse):
    id: uuid.UUID
    employee_id: uuid.UUID
    principal: Money
    start_date: date
    repayment_amount: Money
    repayment_frequency: str
    outstanding_balance: Money
    status: str
    reason: str
    created_by_id: uuid.UUID
    created_at: datetime


class PayrollPaymentResponse(OrmResponse):
    id: uuid.UUID
    payroll_run_id: uuid.UUID
    account_id: uuid.UUID
    payment_date: date
    payment_reference: str
    transaction_ids: list[str]
    paid_by_id: uuid.UUID
    created_at: datetime
    reversed_at: datetime | None


class PayrollReportRow(BaseModel):
    group: str
    employee_count: int
    gross_pay: Money
    paye: Money
    pension: Money
    nhf: Money
    deductions: Money
    net_pay: Money
    employer_cost: Money


class PayrollEmployeeOption(BaseModel):
    id: uuid.UUID
    display_name: str
    employee_number: str | None
    department: str | None
    job_title: str | None
    employment_status: str
