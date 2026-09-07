"""Tenant-scoped voucher workflow and immutable finance-ledger persistence."""

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
from sqlalchemy.orm import Mapped, mapped_column

from meetinghq_api.infrastructure.database import Base
from meetinghq_api.shared.soft_delete import SoftDeleteMixin

MONEY = Numeric(18, 2)


class ExpenseCategory(SoftDeleteMixin, Base):
    """Administrator-configured expense category, scoped to one organization."""

    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_expense_categories_org_name"),
        Index("ix_expense_categories_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VoucherSequence(Base):
    """Daily tenant sequence used to create immutable human voucher numbers."""

    __tablename__ = "voucher_daily_sequences"
    __table_args__ = (UniqueConstraint("organization_id", "sequence_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    sequence_date: Mapped[date] = mapped_column(Date)
    next_sequence: Mapped[int] = mapped_column(Integer, default=1)


class Voucher(SoftDeleteMixin, Base):
    """A controlled expenditure request; amounts are derived and never floats."""

    __tablename__ = "vouchers"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("organization_id", "voucher_number", name="uq_vouchers_org_number"),
        Index("ix_vouchers_org_status_submitted", "organization_id", "status", "submitted_at"),
        Index("ix_vouchers_org_requester_created", "organization_id", "requester_id", "created_at"),
        Index("ix_vouchers_org_department_status", "organization_id", "department_id", "status"),
        CheckConstraint("requested_amount >= 0", name="ck_vouchers_requested_nonnegative"),
        CheckConstraint("approved_amount >= 0", name="ck_vouchers_approved_nonnegative"),
        CheckConstraint("disbursed_amount >= 0", name="ck_vouchers_disbursed_nonnegative"),
        CheckConstraint(
            "disbursed_amount <= approved_amount AND approved_amount <= requested_amount",
            name="ck_vouchers_amount_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_number: Mapped[str] = mapped_column(String(32))
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    expense_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="SET NULL"), index=True
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    requested_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    approved_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    disbursed_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VoucherLineItem(Base):
    __tablename__ = "voucher_line_items"
    __table_args__ = (
        Index("ix_voucher_line_items_voucher_position", "voucher_id", "position"),
        CheckConstraint("quantity > 0", name="ck_voucher_line_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_voucher_line_items_unit_price_nonnegative"),
        CheckConstraint("tax_amount >= 0", name="ck_voucher_line_items_tax_nonnegative"),
        CheckConstraint("amount >= 0", name="ck_voucher_line_items_amount_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    expense_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="SET NULL"), index=True
    )
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("1.000"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    notes: Mapped[str | None] = mapped_column(String(2000))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VoucherReview(Base):
    """An immutable review decision, separate from user comments."""

    __tablename__ = "voucher_reviews"
    __table_args__ = (Index("ix_voucher_reviews_voucher_created", "voucher_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    decision: Mapped[str] = mapped_column(String(24), index=True)
    approved_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoucherComment(SoftDeleteMixin, Base):
    __tablename__ = "voucher_comments"
    __table_args__ = (Index("ix_voucher_comments_voucher_created", "voucher_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VoucherAttachment(SoftDeleteMixin, Base):
    __tablename__ = "voucher_attachments"
    __table_args__ = (Index("ix_voucher_attachments_voucher_created", "voucher_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    url: Mapped[str] = mapped_column(String(1200))
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoucherHistory(Base):
    __tablename__ = "voucher_history"
    __table_args__ = (Index("ix_voucher_history_voucher_created", "voucher_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinanceAccount(SoftDeleteMixin, Base):
    """A financial account whose balance is derived strictly from its ledger."""

    __tablename__ = "finance_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_code", name="uq_finance_accounts_org_code"),
        Index("ix_finance_accounts_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    account_name: Mapped[str] = mapped_column(String(160))
    account_code: Mapped[str] = mapped_column(String(64))
    account_type: Mapped[str] = mapped_column(String(24), index=True)
    bank_name: Mapped[str | None] = mapped_column(String(160))
    account_number_masked: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    opening_balance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(24), default="active")
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FinanceTransaction(Base):
    """Append-only ledger entry. Corrections are represented by reversals."""

    __tablename__ = "finance_transactions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "reference", name="uq_finance_transactions_org_reference"
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_finance_transactions_org_idempotency"
        ),
        Index(
            "ix_finance_transactions_org_account_date",
            "organization_id",
            "account_id",
            "transaction_date",
        ),
        Index("ix_finance_transactions_org_voucher", "organization_id", "voucher_id"),
        Index(
            "ix_finance_transactions_org_reconciled",
            "organization_id",
            "reconciled",
            "transaction_date",
        ),
        Index(
            "ix_finance_transactions_org_transfer_group",
            "organization_id",
            "transfer_group_id",
        ),
        CheckConstraint("amount > 0", name="ck_finance_transactions_amount_positive"),
        CheckConstraint(
            "direction IN ('credit', 'debit')", name="ck_finance_transactions_direction"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT"), index=True
    )
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), index=True
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column()
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance_transactions.id", ondelete="RESTRICT"), unique=True, index=True
    )
    reference: Mapped[str] = mapped_column(String(96))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    transaction_type: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(2000))
    payment_method: Mapped[str | None] = mapped_column(String(32))
    payment_reference: Mapped[str | None] = mapped_column(String(160), index=True)
    beneficiary: Mapped[str | None] = mapped_column(String(240))
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciliation_reference: Mapped[str | None] = mapped_column(String(160))
    reconciliation_note: Mapped[str | None] = mapped_column(String(2000))
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoucherDisbursement(Base):
    __tablename__ = "voucher_disbursements"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_voucher_disbursements_org_idempotency"
        ),
        Index("ix_voucher_disbursements_voucher_date", "voucher_id", "payment_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance_accounts.id", ondelete="RESTRICT"), index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance_transactions.id", ondelete="RESTRICT"), unique=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    payment_method: Mapped[str] = mapped_column(String(32))
    payment_reference: Mapped[str | None] = mapped_column(String(160))
    beneficiary: Mapped[str | None] = mapped_column(String(240))
    note: Mapped[str | None] = mapped_column(Text)
    payment_date: Mapped[date] = mapped_column(Date)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    disbursed_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
