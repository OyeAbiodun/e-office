"""Tenant-scoped, effective-dated Payroll persistence."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base
from meetinghq_api.shared.soft_delete import SoftDeleteMixin

MONEY = Numeric(18, 2)
RATE = Numeric(9, 6)


class SalaryComponent(SoftDeleteMixin, Base):
    """Configurable earning or deduction definition."""

    __tablename__ = "payroll_salary_components"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_payroll_components_org_code"),
        Index("ix_payroll_components_org_active", "organization_id", "is_active"),
        CheckConstraint(
            "component_kind IN ('earning', 'deduction')", name="ck_payroll_component_kind"
        ),
        CheckConstraint(
            "calculation_type IN ('fixed', 'percentage')", name="ck_payroll_component_calc"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(48))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(1000))
    component_kind: Mapped[str] = mapped_column(String(16), index=True)
    calculation_type: Mapped[str] = mapped_column(String(16), default="fixed")
    taxable: Mapped[bool] = mapped_column(Boolean, default=True)
    pensionable: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_start: Mapped[date] = mapped_column(Date, index=True)
    effective_end: Mapped[date | None] = mapped_column(Date, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmployeeSalaryStructure(SoftDeleteMixin, Base):
    """Immutable-in-history employee compensation version."""

    __tablename__ = "payroll_salary_structures"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "employee_id", "effective_start", name="uq_payroll_structure_start"
        ),
        Index(
            "ix_payroll_structure_org_employee_effective",
            "organization_id",
            "employee_id",
            "effective_start",
            "effective_end",
        ),
        CheckConstraint("basic_salary >= 0", name="ck_payroll_structure_basic_nonnegative"),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_payroll_structure_dates",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    basic_salary: Mapped[Decimal] = mapped_column(MONEY)
    effective_start: Mapped[date] = mapped_column(Date, index=True)
    effective_end: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    pension_participates: Mapped[bool] = mapped_column(Boolean, default=True)
    nhf_participates: Mapped[bool] = mapped_column(Boolean, default=True)
    paye_participates: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    change_reason: Mapped[str] = mapped_column(String(1000))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalaryStructureItem(Base):
    __tablename__ = "payroll_salary_structure_items"
    __table_args__ = (
        UniqueConstraint("salary_structure_id", "component_id", name="uq_payroll_structure_item"),
        CheckConstraint("amount >= 0", name="ck_payroll_structure_item_amount"),
        CheckConstraint("percentage >= 0", name="ck_payroll_structure_item_percentage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    salary_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_structures.id", ondelete="CASCADE"), index=True
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_components.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    percentage: Mapped[Decimal] = mapped_column(RATE, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StatutoryConfiguration(Base):
    """Effective-dated statutory/configuration rule snapshot source."""

    __tablename__ = "payroll_statutory_configurations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "configuration_type", "effective_start", name="uq_payroll_stat_start"
        ),
        Index(
            "ix_payroll_stat_org_type_effective",
            "organization_id",
            "configuration_type",
            "effective_start",
            "effective_end",
        ),
        CheckConstraint(
            "configuration_type IN ('paye', 'pension', 'nhf', 'payroll_policy')",
            name="ck_payroll_stat_type",
        ),
        CheckConstraint(
            "effective_end IS NULL OR effective_end >= effective_start",
            name="ck_payroll_stat_dates",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    configuration_type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160))
    effective_start: Mapped[date] = mapped_column(Date, index=True)
    effective_end: Mapped[date | None] = mapped_column(Date, index=True)
    rules: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    change_reason: Mapped[str] = mapped_column(String(1000))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_payroll_period_org_name"),
        Index("ix_payroll_period_org_dates", "organization_id", "start_date", "end_date"),
        CheckConstraint("end_date >= start_date", name="ck_payroll_period_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    payment_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_id", name="uq_payroll_run_period"),
        Index("ix_payroll_run_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_periods.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    prepared_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_reason: Mapped[str | None] = mapped_column(Text)
    paid_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rule_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PayrollEmployeeResult(Base):
    __tablename__ = "payroll_employee_results"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_result_employee"),
        Index("ix_payroll_result_org_employee", "organization_id", "employee_id"),
        Index("ix_payroll_result_org_status", "organization_id", "status"),
        CheckConstraint("gross_pay >= 0", name="ck_payroll_result_gross"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    salary_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payroll_salary_structures.id", ondelete="RESTRICT"), index=True
    )
    employee_name: Mapped[str] = mapped_column(String(180))
    employee_number: Mapped[str | None] = mapped_column(String(64))
    department_name: Mapped[str | None] = mapped_column(String(160))
    job_title: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(24), default="calculated", index=True)
    basic_salary: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    allowances: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    variable_earnings: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    gross_pay: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    taxable_pay: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    paye: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    pension_employee: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    pension_employer: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    nhf: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    loan_deductions: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    other_deductions: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    net_pay: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    employer_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    proration_factor: Mapped[Decimal] = mapped_column(RATE, default=Decimal("1"))
    calculation_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    exceptions: Mapped[list[dict[str, object]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list
    )
    payslip_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollResultItem(Base):
    __tablename__ = "payroll_result_items"
    __table_args__ = (Index("ix_payroll_result_items_result", "payroll_result_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    payroll_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_employee_results.id", ondelete="CASCADE"), index=True
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payroll_salary_components.id", ondelete="SET NULL"), index=True
    )
    code: Mapped[str] = mapped_column(String(48))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    taxable: Mapped[bool] = mapped_column(Boolean, default=False)
    pensionable: Mapped[bool] = mapped_column(Boolean, default=False)
    basis: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)


class PayrollAdjustment(Base):
    __tablename__ = "payroll_adjustments"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_payroll_adjustment_idemp"),
        Index(
            "ix_payroll_adjustment_org_period_employee",
            "organization_id",
            "period_id",
            "employee_id",
        ),
        CheckConstraint("amount > 0", name="ck_payroll_adjustment_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payroll_periods.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    adjustment_type: Mapped[str] = mapped_column(String(24), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reason: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(24), default="approved", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollLoan(SoftDeleteMixin, Base):
    __tablename__ = "payroll_loans"
    __table_args__ = (
        Index("ix_payroll_loan_org_employee_status", "organization_id", "employee_id", "status"),
        CheckConstraint("principal > 0", name="ck_payroll_loan_principal"),
        CheckConstraint("repayment_amount > 0", name="ck_payroll_loan_repayment"),
        CheckConstraint("outstanding_balance >= 0", name="ck_payroll_loan_outstanding"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    principal: Mapped[Decimal] = mapped_column(MONEY)
    start_date: Mapped[date] = mapped_column(Date)
    repayment_amount: Mapped[Decimal] = mapped_column(MONEY)
    repayment_frequency: Mapped[str] = mapped_column(String(24), default="monthly")
    outstanding_balance: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    reason: Mapped[str] = mapped_column(String(1000))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollLoanRepayment(Base):
    __tablename__ = "payroll_loan_repayments"
    __table_args__ = (
        UniqueConstraint("loan_id", "payroll_result_id", name="uq_payroll_loan_result"),
        CheckConstraint("amount > 0", name="ck_payroll_loan_repayment_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payroll_loans.id"), index=True)
    payroll_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_employee_results.id"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(24), default="posted")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayrollPayment(Base):
    __tablename__ = "payroll_payments"
    __table_args__ = (
        UniqueConstraint("organization_id", "payroll_run_id", name="uq_payroll_payment_run"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_payroll_payment_idemp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("finance_accounts.id"), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    payment_reference: Mapped[str] = mapped_column(String(160))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    transaction_ids: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list
    )
    paid_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reversal_reason: Mapped[str | None] = mapped_column(String(2000))


class PayrollHistory(Base):
    __tablename__ = "payroll_history"
    __table_args__ = (Index("ix_payroll_history_run_created", "payroll_run_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
