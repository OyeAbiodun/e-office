"""Voucher and finance API contracts with Decimal-safe money fields."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Money = Decimal


class VoucherLineItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=18, decimal_places=3)
    unit_price: Money = Field(ge=0, max_digits=18, decimal_places=2)
    tax_amount: Money = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    expense_category_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class VoucherCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")
    department_id: uuid.UUID | None = None
    expense_category_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    line_items: list[VoucherLineItemInput] = Field(default_factory=list, max_length=100)


class VoucherUpdate(VoucherCreate):
    title: str | None = Field(default=None, min_length=1, max_length=240)


class VoucherReviewInput(BaseModel):
    approved_amount: Money | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    comment: str | None = Field(default=None, max_length=10000)


class VoucherReturnInput(BaseModel):
    comment: str = Field(min_length=1, max_length=10000)


class VoucherCommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class ExpenseCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class FinanceAccountInput(BaseModel):
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


class DisbursementInput(BaseModel):
    account_id: uuid.UUID
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: Literal["bank_transfer", "cash", "cheque"]
    payment_reference: str | None = Field(default=None, max_length=160)
    beneficiary: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=10000)
    payment_date: date
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReversalInput(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReconciliationInput(BaseModel):
    reference: str = Field(min_length=1, max_length=160)
    note: str | None = Field(default=None, max_length=2000)


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


class FinanceTransactionResponse(OrmResponse):
    id: uuid.UUID
    account_id: uuid.UUID
    voucher_id: uuid.UUID | None
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
