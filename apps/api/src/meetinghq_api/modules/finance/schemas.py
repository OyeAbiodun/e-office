"""Voucher and finance API contracts with Decimal-safe money fields."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

Money = Decimal


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class VoucherLineItemInput(InputModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=18, decimal_places=3)
    unit_price: Money = Field(ge=0, max_digits=18, decimal_places=2)
    tax_amount: Money = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    expense_category_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class VoucherCreate(InputModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")
    department_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    line_items: list[VoucherLineItemInput] = Field(default_factory=list, max_length=100)


class VoucherUpdate(InputModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    department_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    line_items: list[VoucherLineItemInput] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def required_values(self) -> VoucherUpdate:
        for name in ("title", "currency", "line_items"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class VoucherReviewInput(InputModel):
    approved_amount: Money | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    comment: str | None = Field(default=None, max_length=10000)


class VoucherReturnInput(InputModel):
    comment: str = Field(min_length=1, max_length=10000)


class VoucherCommentInput(InputModel):
    body: str = Field(min_length=1, max_length=20000)


class ExpenseCategoryInput(InputModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class FinanceAccountInput(InputModel):
    account_name: str = Field(min_length=1, max_length=160)
    account_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    account_type: Literal["bank", "cash"]
    bank_name: str | None = Field(default=None, max_length=160)
    account_number: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")
    opening_balance: Money = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    status: Literal["active", "inactive"] = "active"
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("account_number")
    @classmethod
    def safe_account_number(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class DisbursementInput(InputModel):
    account_id: uuid.UUID
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: Literal["bank_transfer", "cash", "cheque"]
    payment_reference: str | None = Field(default=None, max_length=160)
    beneficiary: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=10000)
    payment_date: date
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReversalInput(InputModel):
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReconciliationInput(InputModel):
    reference: str = Field(min_length=1, max_length=160)
    note: str | None = Field(default=None, max_length=2000)


class FinanceAdjustmentInput(InputModel):
    """A deliberately controlled non-voucher ledger correction."""

    account_id: uuid.UUID
    direction: Literal["credit", "debit"]
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    transaction_date: date
    description: str = Field(min_length=1, max_length=2000)
    reference: str | None = Field(default=None, max_length=96)
    idempotency_key: str = Field(min_length=8, max_length=128)


class FinanceTransferInput(InputModel):
    """Move funds between two active accounts in one atomic ledger operation."""

    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    transaction_date: date
    description: str = Field(min_length=1, max_length=2000)
    reference: str | None = Field(default=None, max_length=96)
    idempotency_key: str = Field(min_length=8, max_length=128)


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VoucherLineItemResponse(OrmResponse):
    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Money
    tax_amount: Money
    amount: Money
    expense_category_id: uuid.UUID | None
    notes: str | None
    position: int


class VoucherResponse(OrmResponse):
    id: uuid.UUID
    voucher_number: str
    requester_id: uuid.UUID
    department_id: uuid.UUID | None
    expense_category_id: uuid.UUID | None
    meeting_id: uuid.UUID | None
    task_id: uuid.UUID | None
    title: str
    description: str | None
    currency: str
    requested_amount: Money
    approved_amount: Money
    disbursed_amount: Money
    status: str
    submitted_at: datetime | None
    approved_at: datetime | None
    returned_at: datetime | None
    rejected_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    requester_name: str | None = None
    department_name: str | None = None
    meeting_title: str | None = None
    task_title: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def outstanding_amount(self) -> Money:
        return self.approved_amount - self.disbursed_amount


class VoucherDetailResponse(BaseModel):
    voucher: VoucherResponse
    line_items: list[VoucherLineItemResponse]
    reviews: list[dict[str, object]]
    comments: list[dict[str, object]]
    attachments: list[dict[str, object]]
    history: list[dict[str, object]]
    disbursements: list[dict[str, object]]
    transactions: list[FinanceTransactionResponse] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)


class FinanceAccountResponse(OrmResponse):
    id: uuid.UUID
    account_name: str
    account_code: str
    account_type: str
    bank_name: str | None
    account_number_masked: str | None
    currency: str
    opening_balance: Money
    status: str
    description: str | None
    balance: Money = Decimal("0.00")


class FinanceTransactionResponse(OrmResponse):
    id: uuid.UUID
    account_id: uuid.UUID
    voucher_id: uuid.UUID | None
    transfer_group_id: uuid.UUID | None
    reversal_of_id: uuid.UUID | None
    reference: str
    transaction_type: str
    direction: str
    amount: Money
    currency: str
    transaction_date: date
    description: str
    payment_method: str | None
    payment_reference: str | None
    beneficiary: str | None
    reconciled: bool
    reconciled_at: datetime | None
    reconciliation_reference: str | None
    reconciliation_note: str | None
    created_at: datetime
    account_name: str | None = None
    voucher_number: str | None = None
    running_balance: Money | None = None


class StatementResponse(BaseModel):
    account: FinanceAccountResponse
    from_date: date
    to_date: date
    opening_balance: Money
    credits: Money
    debits: Money
    closing_balance: Money
    transactions: list[FinanceTransactionResponse]


class VoucherPage(BaseModel):
    items: list[VoucherResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FinanceTransactionPage(BaseModel):
    items: list[FinanceTransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VoucherFilters(InputModel):
    search: str | None = Field(default=None, max_length=200)
    status: str | None = None
    requester_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    approver_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None
    min_amount: Money | None = Field(default=None, ge=0)
    max_amount: Money | None = Field(default=None, ge=0)
    sort: Literal["created", "submitted", "amount", "status", "number"] = "created"
    direction: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: Literal[10, 25, 50, 100] = 25


class AttachmentResponse(OrmResponse):
    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    uploaded_by_id: uuid.UUID
    created_at: datetime
    url: str
