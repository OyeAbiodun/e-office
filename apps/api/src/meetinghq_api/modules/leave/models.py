"""Auditable, tenant-scoped Leave Management persistence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base
from meetinghq_api.shared.soft_delete import SoftDeleteMixin

MONEY = Numeric(18, 2)


class LeaveType(SoftDeleteMixin, Base):
    __tablename__ = "leave_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_leave_types_org_code"),
        Index("ix_leave_types_org_active", "organization_id", "is_active"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    default_entitlement: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    accrual_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    accrual_frequency: Mapped[str | None] = mapped_column(String(16))
    carryover_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    carryover_limit: Mapped[Decimal | None] = mapped_column(MONEY)
    carryover_expiry_months: Mapped[int | None] = mapped_column()
    minimum_notice_days: Mapped[int] = mapped_column(default=0)
    maximum_consecutive_days: Mapped[int | None] = mapped_column()
    attachment_required: Mapped[bool] = mapped_column(Boolean, default=False)
    half_day_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    eligible_employment_types: Mapped[str | None] = mapped_column(Text)
    probation_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeavePeriod(Base):
    __tablename__ = "leave_periods"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_leave_periods_org_name"),
        Index("ix_leave_periods_org_dates", "organization_id", "start_date", "end_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeaveEntitlement(Base):
    __tablename__ = "leave_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employee_id",
            "leave_type_id",
            "leave_period_id",
            name="uq_leave_entitlement_period",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"), index=True
    )
    leave_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_periods.id", ondelete="RESTRICT"), index=True
    )
    allocated_days: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeaveBalanceLedgerEntry(Base):
    __tablename__ = "leave_balance_ledger_entries"
    __table_args__ = (
        Index(
            "ix_leave_ledger_org_employee_type_period",
            "organization_id",
            "employee_id",
            "leave_type_id",
            "leave_period_id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_entitlements.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"), index=True
    )
    leave_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_periods.id", ondelete="RESTRICT"), index=True
    )
    entry_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeaveRequest(SoftDeleteMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        Index(
            "ix_leave_requests_org_employee_dates",
            "organization_id",
            "employee_id",
            "start_date",
            "end_date",
        ),
        Index("ix_leave_requests_org_status", "organization_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"), index=True
    )
    leave_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_periods.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    duration_days: Mapped[Decimal] = mapped_column(MONEY)
    half_day: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    calendar_event_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeaveAttachment(SoftDeleteMixin, Base):
    """Private supporting document reference; storage access is always authenticated."""

    __tablename__ = "leave_attachments"
    __table_args__ = (
        Index("ix_leave_attachments_request_created", "leave_request_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column()
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeaveRequestHistory(Base):
    __tablename__ = "leave_request_history"
    __table_args__ = (Index("ix_leave_history_request_created", "leave_request_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_requests.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
