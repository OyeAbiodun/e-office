"""Voucher and finance HTTP boundary with permission-first workflow routes."""

import asyncio
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.finance import exports
from meetinghq_api.modules.finance.documents import MAX_BYTES, VoucherDocuments
from meetinghq_api.modules.finance.models import (
    ExpenseCategory,
    FinanceTransaction,
    Voucher,
)
from meetinghq_api.modules.finance.queries import FinanceQueries
from meetinghq_api.modules.finance.schemas import (
    AttachmentResponse,
    DisbursementInput,
    ExpenseCategoryInput,
    FinanceAccountInput,
    FinanceAccountResponse,
    FinanceTransactionPage,
    FinanceTransactionResponse,
    ReconciliationInput,
    ReversalInput,
    StatementResponse,
    VoucherCommentInput,
    VoucherCreate,
    VoucherDetailResponse,
    VoucherFilters,
    VoucherPage,
    VoucherResponse,
    VoucherReturnInput,
    VoucherReviewInput,
    VoucherUpdate,
)
from meetinghq_api.modules.finance.service import FinanceService
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization, OrganizationUnit
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.responses import OperationResponse

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
    filters: Annotated[VoucherFilters, Query()],
) -> VoucherPage:
    return await FinanceQueries(service(session, settings)).vouchers(user, filters)


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
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.accounts.view")],
) -> list[FinanceAccountResponse]:
    return await FinanceQueries(service(session, settings)).accounts(user)


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
    session.add(
        AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action="finance.category_created",
            resource="expense_category",
            resource_id=item.id,
            audit_metadata={"name": item.name},
        )
    )
    return {"id": str(item.id), "name": item.name}


def download(data: bytes, filename: str, content_type: str) -> Response:
    return Response(
        data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/vouchers/export")
async def export_vouchers(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.export")],
    filters: Annotated[VoucherFilters, Query()],
) -> Response:
    queries = FinanceQueries(service(session, settings))
    query = queries.vouchers_query(user, filters)
    rows = list((await session.scalars(query.limit(10001))).all())
    if len(rows) > 10000:
        raise ValidationError("Narrow the filters to export at most 10,000 vouchers")
    return download(
        exports.voucher_csv(await queries.enrich(user, rows)), "vouchers.csv", "text/csv"
    )


@router.get("/vouchers/options")
async def voucher_options(
    session: Session, settings: AppSettings, user: VoucherReader
) -> dict[str, object]:
    svc = service(session, settings)
    visible = select(Voucher.requester_id).where(
        Voucher.organization_id == user.organization_id, svc.visible(user)
    )
    users = (
        await session.scalars(
            select(User).where(User.organization_id == user.organization_id, User.id.in_(visible))
        )
    ).all()
    departments = (
        await session.scalars(
            select(OrganizationUnit).where(
                OrganizationUnit.organization_id == user.organization_id,
                OrganizationUnit.deleted_at.is_(None),
                OrganizationUnit.id.in_(
                    {u.department_id for u in [*users, user] if u.department_id}
                ),
            )
        )
    ).all()
    from meetinghq_api.modules.finance.models import VoucherReview

    reviewers = (
        await session.scalars(
            select(User).where(
                User.organization_id == user.organization_id,
                User.id.in_(
                    select(VoucherReview.reviewer_id)
                    .join(Voucher, Voucher.id == VoucherReview.voucher_id)
                    .where(Voucher.organization_id == user.organization_id, svc.visible(user))
                ),
            )
        )
    ).all()
    return {
        "requesters": [
            {"id": str(u.id), "name": f"{u.first_name} {u.last_name or ''}".strip()} for u in users
        ],
        "approvers": [
            {"id": str(u.id), "name": f"{u.first_name} {u.last_name or ''}".strip()}
            for u in reviewers
        ],
        "departments": [{"id": str(d.id), "name": d.name} for d in departments],
    }


@router.get("/vouchers/summary")
async def voucher_summary(
    session: Session, settings: AppSettings, user: VoucherReader
) -> dict[str, object]:
    svc = service(session, settings)
    rows = (
        await session.execute(
            select(
                Voucher.status,
                Voucher.currency,
                func.count(Voucher.id),
                func.sum(Voucher.approved_amount - Voucher.disbursed_amount),
            )
            .where(
                Voucher.organization_id == user.organization_id,
                Voucher.deleted_at.is_(None),
                svc.visible(user),
            )
            .group_by(Voucher.status, Voucher.currency)
        )
    ).all()
    return {
        "groups": [
            {"status": s, "currency": c, "count": n, "outstanding": str(v)} for s, c, n, v in rows
        ]
    }


@router.get("/vouchers/{voucher_id}", response_model=VoucherDetailResponse)
async def voucher_detail(
    voucher_id: uuid.UUID, session: Session, settings: AppSettings, user: VoucherReader
) -> VoucherDetailResponse:
    return await FinanceQueries(service(session, settings)).detail(user, voucher_id)


@router.get("/vouchers/{voucher_id}/pdf")
async def export_voucher_pdf(
    voucher_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.export")],
) -> Response:
    detail = await FinanceQueries(service(session, settings)).detail(user, voucher_id)
    name = await session.scalar(
        select(Organization.name).where(Organization.id == user.organization_id)
    )
    data = await asyncio.to_thread(exports.voucher_pdf, detail, name or "MeetingHQ")
    return download(data, f"{detail.voucher.voucher_number}.pdf", "application/pdf")


@router.post("/vouchers/{voucher_id}/comments", status_code=201)
async def comment_voucher(
    voucher_id: uuid.UUID,
    body: VoucherCommentInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.comment")],
) -> OperationResponse:
    await VoucherDocuments(service(session, settings), settings).comment(
        user, voucher_id, body.body
    )
    return OperationResponse(message="Comment added")


@router.post(
    "/vouchers/{voucher_id}/attachments", response_model=AttachmentResponse, status_code=201
)
async def upload_attachment(
    voucher_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.edit_draft")],
    file: Annotated[UploadFile, File()],
) -> AttachmentResponse:
    documents = VoucherDocuments(service(session, settings), settings)
    voucher = await documents.editable(user, voucher_id)
    content = await file.read(MAX_BYTES + 1)
    return await documents.upload(
        user,
        voucher,
        file.filename or "document",
        file.content_type or "application/octet-stream",
        content,
    )


@router.get("/vouchers/{voucher_id}/attachments", response_model=list[dict[str, object]])
async def list_attachments(
    voucher_id: uuid.UUID, session: Session, settings: AppSettings, user: VoucherReader
) -> list[dict[str, object]]:
    return (await FinanceQueries(service(session, settings)).detail(user, voucher_id)).attachments


@router.get("/vouchers/{voucher_id}/attachments/{attachment_id}/download")
async def download_attachment(
    voucher_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: VoucherReader,
) -> FileResponse:
    row = await VoucherDocuments(service(session, settings), settings).attachment(
        user, voucher_id, attachment_id
    )
    target = await asyncio.to_thread(document_path, settings.local_storage_path, row.storage_key)
    if target is None:
        raise NotFoundError("Voucher document not found")
    return FileResponse(
        target,
        media_type=row.content_type,
        filename=row.filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def document_path(root_path: str, key: str) -> Path | None:
    root = Path(root_path).resolve()
    target = (root / key).resolve()
    return target if root in target.parents and target.is_file() else None


@router.delete("/vouchers/{voucher_id}/attachments/{attachment_id}")
async def delete_attachment(
    voucher_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("vouchers.edit_draft")],
) -> OperationResponse:
    await VoucherDocuments(service(session, settings), settings).delete(
        user, voucher_id, attachment_id
    )
    return OperationResponse(message="Document removed")


@router.get("/finance/transactions/page", response_model=FinanceTransactionPage)
async def transaction_page(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.transactions.view")],
    account_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=200),
    reconciled: bool | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=10, le=100),
) -> FinanceTransactionPage:
    return await FinanceQueries(service(session, settings)).transactions(
        user,
        account_id=account_id,
        search=search,
        reconciled=reconciled,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


@router.get("/finance/transactions/export")
async def transaction_export(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.export")],
    account_id: uuid.UUID | None = None,
    search: str | None = None,
    reconciled: bool | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> Response:
    service(session, settings).require(user, "finance.transactions.view")
    page = await FinanceQueries(service(session, settings)).transactions(
        user,
        account_id=account_id,
        search=search,
        reconciled=reconciled,
        from_date=from_date,
        to_date=to_date,
        page_size=10001,
    )
    if page.total > 10000:
        raise ValidationError("Narrow the filters to export at most 10,000 transactions")
    return download(exports.transaction_csv(page.items), "transactions.csv", "text/csv")


@router.get("/finance/accounts/{account_id}", response_model=FinanceAccountResponse)
async def account_detail(
    account_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.accounts.view")],
) -> FinanceAccountResponse:
    svc = service(session, settings)
    row = await svc._account(user, account_id)
    result = FinanceAccountResponse.model_validate(row)
    result.balance = await svc.account_balance(row)
    return result


@router.get("/finance/accounts/{account_id}/statement", response_model=StatementResponse)
async def account_statement(
    account_id: uuid.UUID,
    from_date: date,
    to_date: date,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.transactions.view")],
) -> StatementResponse:
    return await FinanceQueries(service(session, settings)).statement(
        user, account_id, from_date, to_date
    )


@router.get("/finance/accounts/{account_id}/statement/export")
async def statement_export(
    account_id: uuid.UUID,
    from_date: date,
    to_date: date,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("finance.export")],
    format: Literal["csv", "pdf"] = "csv",
) -> Response:
    svc = service(session, settings)
    svc.require(user, "finance.transactions.view")
    statement = await FinanceQueries(svc).statement(user, account_id, from_date, to_date)
    if format == "csv":
        return download(exports.statement_csv(statement), "statement.csv", "text/csv")
    name = await session.scalar(
        select(Organization.name).where(Organization.id == user.organization_id)
    )
    data = await asyncio.to_thread(exports.statement_pdf, statement, name or "MeetingHQ")
    return download(data, "statement.pdf", "application/pdf")
