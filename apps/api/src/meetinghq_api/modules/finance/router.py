"""Voucher and finance HTTP boundary with permission-first workflow routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.finance.models import (
    ExpenseCategory,
    FinanceAccount,
    FinanceTransaction,
    Voucher,
)
from meetinghq_api.modules.finance.schemas import (
    DisbursementInput,
    ExpenseCategoryInput,
    FinanceAccountInput,
    FinanceAccountResponse,
    FinanceTransactionResponse,
    ReconciliationInput,
    ReversalInput,
    VoucherCreate,
    VoucherPage,
    VoucherResponse,
    VoucherReturnInput,
    VoucherReviewInput,
    VoucherUpdate,
)
from meetinghq_api.modules.finance.service import FinanceService
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.users.models import User

router = APIRouter(tags=["finance"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def service(session: Session, settings: AppSettings) -> FinanceService:
    return FinanceService(session, NotificationService(session, settings))


VoucherReader = Annotated[User, require_permission("vouchers.view_own")]
VoucherCreator = Annotated[User, require_permission("vouchers.create")]


@router.get("/vouchers", response_model=VoucherPage)
async def list_vouchers(
    session: Session,
    settings: AppSettings,
    user: VoucherReader,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=10, le=100),
) -> VoucherPage:
    query = select(Voucher).where(
        Voucher.organization_id == user.organization_id, Voucher.deleted_at.is_(None)
    )
    if "vouchers.audit" not in {p.name for r in user.roles for p in r.permissions}:
        query = query.where(Voucher.requester_id == user.id)
    if status_filter:
        query = query.where(Voucher.status == status_filter)
    if search:
        query = query.where(Voucher.title.ilike(f"%{search.strip()}%"))
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                query.order_by(Voucher.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return VoucherPage(
        items=[VoucherResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/vouchers", response_model=VoucherResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    body: VoucherCreate, session: Session, settings: AppSettings, user: VoucherCreator
) -> VoucherResponse:
    return VoucherResponse.model_validate(await service(session, settings).create(user, body))


@router.patch("/vouchers/{voucher_id}", response_model=VoucherResponse)
async def edit_voucher(
    voucher_id: uuid.UUID,
    body: VoucherUpdate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.edit_draft")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(
        await service(session, settings).update_draft(user, voucher_id, body)
    )


@router.post("/vouchers/{voucher_id}/submit", response_model=VoucherResponse)
async def submit_voucher(
    voucher_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.submit")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(await service(session, settings).submit(user, voucher_id))


@router.post("/vouchers/{voucher_id}/approve", response_model=VoucherResponse)
async def approve_voucher(
    voucher_id: uuid.UUID,
    body: VoucherReviewInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.approve")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(
        await service(session, settings).review(user, voucher_id, "approved", body)
    )


@router.post("/vouchers/{voucher_id}/return", response_model=VoucherResponse)
async def return_voucher(
    voucher_id: uuid.UUID,
    body: VoucherReturnInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.return")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(
        await service(session, settings).review(user, voucher_id, "returned", body)
    )


@router.post("/vouchers/{voucher_id}/reject", response_model=VoucherResponse)
async def reject_voucher(
    voucher_id: uuid.UUID,
    body: VoucherReturnInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.reject")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(
        await service(session, settings).review(user, voucher_id, "rejected", body)
    )


@router.post("/vouchers/{voucher_id}/disburse", response_model=VoucherResponse)
async def disburse_voucher(
    voucher_id: uuid.UUID,
    body: DisbursementInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.disburse")],
) -> VoucherResponse:
    return VoucherResponse.model_validate(
        await service(session, settings).disburse(user, voucher_id, body)
    )


@router.get("/finance/accounts", response_model=list[FinanceAccountResponse])
async def accounts(
    session: Session, user: Annotated[User, require_permission("finance.accounts.view")]
) -> list[FinanceAccountResponse]:
    rows = list(
        (
            await session.scalars(
                select(FinanceAccount)
                .where(
                    FinanceAccount.organization_id == user.organization_id,
                    FinanceAccount.deleted_at.is_(None),
                )
                .order_by(FinanceAccount.account_name)
            )
        ).all()
    )
    return [FinanceAccountResponse.model_validate(row) for row in rows]


@router.post(
    "/finance/accounts", response_model=FinanceAccountResponse, status_code=status.HTTP_201_CREATED
)
async def create_account(
    body: FinanceAccountInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.accounts.manage")],
) -> FinanceAccountResponse:
    return FinanceAccountResponse.model_validate(
        await service(session, settings).create_account(user, body)
    )


@router.get("/finance/transactions", response_model=list[FinanceTransactionResponse])
async def transactions(
    session: Session, user: Annotated[User, require_permission("finance.transactions.view")]
) -> list[FinanceTransactionResponse]:
    rows = list(
        (
            await session.scalars(
                select(FinanceTransaction)
                .where(FinanceTransaction.organization_id == user.organization_id)
                .order_by(FinanceTransaction.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    return [FinanceTransactionResponse.model_validate(row) for row in rows]


@router.post(
    "/finance/transactions/{transaction_id}/reverse", response_model=FinanceTransactionResponse
)
async def reverse_transaction(
    transaction_id: uuid.UUID,
    body: ReversalInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.reverse")],
) -> FinanceTransactionResponse:
    return FinanceTransactionResponse.model_validate(
        await service(session, settings).reverse(user, transaction_id, body)
    )


@router.post(
    "/finance/transactions/{transaction_id}/reconcile", response_model=FinanceTransactionResponse
)
async def reconcile_transaction(
    transaction_id: uuid.UUID,
    body: ReconciliationInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.reconcile")],
) -> FinanceTransactionResponse:
    return FinanceTransactionResponse.model_validate(
        await service(session, settings).reconcile(user, transaction_id, body)
    )


@router.get("/finance/categories", response_model=list[dict[str, object]])
async def categories(session: Session, user: VoucherReader) -> list[dict[str, object]]:
    rows = list(
        (
            await session.scalars(
                select(ExpenseCategory)
                .where(
                    ExpenseCategory.organization_id == user.organization_id,
                    ExpenseCategory.deleted_at.is_(None),
                )
                .order_by(ExpenseCategory.name)
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "description": row.description,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@router.post("/finance/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    body: ExpenseCategoryInput,
    session: Session,
    user: Annotated[User, require_permission("finance.accounts.manage")],
) -> dict[str, object]:
    item = ExpenseCategory(
        organization_id=user.organization_id,
        name=body.name.strip(),
        description=body.description,
        is_active=body.is_active,
    )
    session.add(item)
    await session.flush()
    return {"id": str(item.id), "name": item.name}
