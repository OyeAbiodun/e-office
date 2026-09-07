"""Tenant- and workflow-scoped financial read models and exact statements."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.sql import Select

from meetinghq_api.modules.finance.models import (
    FinanceAccount,
    FinanceTransaction,
    Voucher,
    VoucherAttachment,
    VoucherComment,
    VoucherDisbursement,
    VoucherHistory,
    VoucherLineItem,
    VoucherReview,
)
from meetinghq_api.modules.finance.schemas import (
    FinanceAccountResponse,
    FinanceTransactionPage,
    FinanceTransactionResponse,
    StatementResponse,
    VoucherDetailResponse,
    VoucherFilters,
    VoucherLineItemResponse,
    VoucherPage,
    VoucherResponse,
)
from meetinghq_api.modules.finance.service import OPEN_EDITABLE, ZERO, FinanceService
from meetinghq_api.modules.meetings.models import Meeting
from meetinghq_api.modules.organizations.models import OrganizationUnit
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import ValidationError


class FinanceQueries:
    def __init__(self, service: FinanceService) -> None:
        self.service = service
        self.session = service.session

    def vouchers_query(self, actor: User, filters: VoucherFilters) -> Select[tuple[Voucher]]:
        query = select(Voucher).where(
            Voucher.organization_id == actor.organization_id,
            Voucher.deleted_at.is_(None),
            self.service.visible(actor),
        )
        if filters.search:
            needle = f"%{filters.search}%"
            query = query.where(
                or_(Voucher.title.ilike(needle), Voucher.voucher_number.ilike(needle))
            )
        for name in ("status", "requester_id", "department_id"):
            if (value := getattr(filters, name)) is not None:
                query = query.where(getattr(Voucher, name) == value)
        if filters.approver_id:
            query = query.where(
                Voucher.id.in_(
                    select(VoucherReview.voucher_id).where(
                        VoucherReview.organization_id == actor.organization_id,
                        VoucherReview.reviewer_id == filters.approver_id,
                        VoucherReview.decision == "approved",
                    )
                )
            )
        if filters.from_date:
            query = query.where(
                Voucher.created_at >= datetime.combine(filters.from_date, time.min, UTC)
            )
        if filters.to_date:
            query = query.where(
                Voucher.created_at
                < datetime.combine(filters.to_date + timedelta(days=1), time.min, UTC)
            )
        if filters.min_amount is not None:
            query = query.where(Voucher.requested_amount >= filters.min_amount)
        if filters.max_amount is not None:
            query = query.where(Voucher.requested_amount <= filters.max_amount)
        column = {
            "created": Voucher.created_at,
            "submitted": Voucher.submitted_at,
            "amount": Voucher.requested_amount,
            "status": Voucher.status,
            "number": Voucher.voucher_number,
        }[filters.sort]
        return query.order_by(
            column.asc() if filters.direction == "asc" else column.desc(), Voucher.id
        )

    async def enrich(self, actor: User, rows: list[Voucher]) -> list[VoucherResponse]:
        users = {
            row.id: row
            for row in (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == actor.organization_id,
                        User.id.in_({v.requester_id for v in rows}),
                    )
                )
            ).all()
        }
        departments = {
            key: value
            for key, value in (
                await self.session.execute(
                    select(OrganizationUnit.id, OrganizationUnit.name).where(
                        OrganizationUnit.organization_id == actor.organization_id,
                        OrganizationUnit.id.in_({v.department_id for v in rows if v.department_id}),
                    )
                )
            ).all()
        }
        meetings = {
            key: value
            for key, value in (
                await self.session.execute(
                    select(Meeting.id, Meeting.title).where(
                        Meeting.organization_id == actor.organization_id,
                        Meeting.id.in_({v.meeting_id for v in rows if v.meeting_id}),
                    )
                )
            ).all()
        }
        result = []
        for row in rows:
            item = VoucherResponse.model_validate(row)
            if user := users.get(row.requester_id):
                item.requester_name = f"{user.first_name} {user.last_name or ''}".strip()
            item.department_name = departments.get(row.department_id) if row.department_id else None
            item.meeting_title = meetings.get(row.meeting_id) if row.meeting_id else None
            result.append(item)
        return result

    async def vouchers(self, actor: User, filters: VoucherFilters) -> VoucherPage:
        query = self.vouchers_query(actor, filters)
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(query.order_by(None).subquery())
            )
            or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
                )
            ).all()
        )
        return VoucherPage(
            items=await self.enrich(actor, rows),
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=max(1, (total + filters.page_size - 1) // filters.page_size),
        )

    async def detail(self, actor: User, voucher_id: uuid.UUID) -> VoucherDetailResponse:
        voucher = await self.service._voucher(actor, voucher_id)
        # Load names once for the complete timeline; never issue one query per history row.
        names = {
            row.id: f"{row.first_name} {row.last_name or ''}".strip()
            for row in (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == actor.organization_id,
                        User.id.in_(
                            select(VoucherHistory.actor_id).where(
                                VoucherHistory.voucher_id == voucher.id
                            )
                        ),
                    )
                )
            ).all()
        }
        collections: dict[str, list[dict[str, object]]] = {}
        for key, model, fields, person in (
            (
                "reviews",
                VoucherReview,
                ("id", "decision", "approved_amount", "comment", "created_at", "reviewer_id"),
                "reviewer_id",
            ),
            ("comments", VoucherComment, ("id", "body", "created_at", "author_id"), "author_id"),
            (
                "attachments",
                VoucherAttachment,
                ("id", "filename", "content_type", "size", "created_at", "uploaded_by_id", "url"),
                "uploaded_by_id",
            ),
            (
                "history",
                VoucherHistory,
                ("id", "event_type", "reason", "payload", "created_at", "actor_id"),
                "actor_id",
            ),
            (
                "disbursements",
                VoucherDisbursement,
                (
                    "id",
                    "amount",
                    "currency",
                    "payment_method",
                    "payment_reference",
                    "payment_date",
                    "beneficiary",
                    "note",
                    "transaction_id",
                    "created_at",
                    "disbursed_by_id",
                ),
                "disbursed_by_id",
            ),
        ):
            query = select(model).where(
                model.organization_id == actor.organization_id, model.voucher_id == voucher.id
            )
            if model in (VoucherComment, VoucherAttachment):
                query = query.where(model.deleted_at.is_(None))
            items = []
            for row in (await self.session.scalars(query.order_by(model.created_at))).all():
                item = {field: getattr(row, field) for field in fields}
                item["actor_name"] = names.get(getattr(row, person))
                items.append(item)
            collections[key] = items
        actions = []
        permissions = self.service._permissions(actor)
        if voucher.requester_id == actor.id and voucher.status in OPEN_EDITABLE:
            actions += [
                a
                for a, p in (("edit", "edit_draft"), ("submit", "submit"))
                if f"vouchers.{p}" in permissions
            ]
        if voucher.requester_id != actor.id and voucher.status == "submitted":
            managed = "vouchers.view_all" in permissions or bool(
                await self.session.scalar(
                    select(Voucher.id).where(
                        Voucher.id == voucher.id, self.service.managed_requesters(actor)
                    )
                )
            )
            if managed:
                actions += [
                    a for a in ("approve", "return", "reject") if f"vouchers.{a}" in permissions
                ]
        approvers = {
            r["reviewer_id"] for r in collections["reviews"] if r["decision"] == "approved"
        }
        if (
            voucher.status in {"approved", "partially_disbursed"}
            and actor.id != voucher.requester_id
            and actor.id not in approvers
            and "vouchers.disburse" in permissions
        ):
            actions.append("disburse")
        if "vouchers.comment" in permissions:
            actions.append("comment")
        lines = list(
            (
                await self.session.scalars(
                    select(VoucherLineItem)
                    .where(
                        VoucherLineItem.organization_id == actor.organization_id,
                        VoucherLineItem.voucher_id == voucher.id,
                    )
                    .order_by(VoucherLineItem.position)
                )
            ).all()
        )
        transactions = list(
            (
                await self.session.scalars(
                    select(FinanceTransaction)
                    .where(
                        FinanceTransaction.organization_id == actor.organization_id,
                        FinanceTransaction.voucher_id == voucher.id,
                    )
                    .order_by(FinanceTransaction.created_at)
                )
            ).all()
        )
        return VoucherDetailResponse(
            voucher=(await self.enrich(actor, [voucher]))[0],
            line_items=[VoucherLineItemResponse.model_validate(r) for r in lines],
            reviews=collections["reviews"],
            comments=collections["comments"],
            attachments=collections["attachments"],
            history=collections["history"],
            disbursements=collections["disbursements"],
            allowed_actions=actions,
            transactions=[FinanceTransactionResponse.model_validate(t) for t in transactions],
        )

    async def accounts(self, actor: User) -> list[FinanceAccountResponse]:
        amounts = (
            select(
                FinanceTransaction.account_id,
                func.sum(
                    case(
                        (FinanceTransaction.direction == "credit", FinanceTransaction.amount),
                        else_=-FinanceTransaction.amount,
                    )
                ).label("movement"),
            )
            .where(FinanceTransaction.organization_id == actor.organization_id)
            .group_by(FinanceTransaction.account_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(FinanceAccount, amounts.c.movement)
                .outerjoin(amounts, FinanceAccount.id == amounts.c.account_id)
                .where(
                    FinanceAccount.organization_id == actor.organization_id,
                    FinanceAccount.deleted_at.is_(None),
                )
                .order_by(FinanceAccount.account_name)
            )
        ).all()
        result = []
        for account, movement in rows:
            item = FinanceAccountResponse.model_validate(account)
            item.balance = self.service._money(account.opening_balance + Decimal(movement or ZERO))
            result.append(item)
        return result

    async def transactions(
        self,
        actor: User,
        *,
        account_id: uuid.UUID | None = None,
        search: str | None = None,
        reconciled: bool | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> FinanceTransactionPage:
        query = (
            select(FinanceTransaction, FinanceAccount.account_name, Voucher.voucher_number)
            .join(FinanceAccount, FinanceAccount.id == FinanceTransaction.account_id)
            .outerjoin(Voucher, Voucher.id == FinanceTransaction.voucher_id)
            .where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceAccount.organization_id == actor.organization_id,
            )
        )
        if account_id:
            await self.service._account(actor, account_id)
            query = query.where(FinanceTransaction.account_id == account_id)
        if search:
            query = query.where(
                or_(
                    FinanceTransaction.reference.ilike(f"%{search}%"),
                    FinanceTransaction.description.ilike(f"%{search}%"),
                )
            )
        if reconciled is not None:
            query = query.where(FinanceTransaction.reconciled == reconciled)
        if from_date:
            query = query.where(FinanceTransaction.transaction_date >= from_date)
        if to_date:
            query = query.where(FinanceTransaction.transaction_date <= to_date)
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = (
            await self.session.execute(
                query.order_by(
                    FinanceTransaction.transaction_date.desc(),
                    FinanceTransaction.created_at.desc(),
                    FinanceTransaction.id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items = []
        for transaction, name, number in rows:
            item = FinanceTransactionResponse.model_validate(transaction)
            item.account_name, item.voucher_number = name, number
            items.append(item)
        return FinanceTransactionPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
        )

    async def statement(
        self, actor: User, account_id: uuid.UUID, start: date, end: date
    ) -> StatementResponse:
        if end < start:
            raise ValidationError("End date must be on or after start date")
        account = await self.service._account(actor, account_id)
        movement = case(
            (FinanceTransaction.direction == "credit", FinanceTransaction.amount),
            else_=-FinanceTransaction.amount,
        )
        base = [
            FinanceTransaction.organization_id == actor.organization_id,
            FinanceTransaction.account_id == account.id,
        ]
        prior = await self.session.scalar(
            select(func.sum(movement)).where(*base, FinanceTransaction.transaction_date < start)
        )
        opening = self.service._money(account.opening_balance + Decimal(prior or ZERO))
        rows = list(
            (
                await self.session.scalars(
                    select(FinanceTransaction)
                    .where(
                        *base,
                        FinanceTransaction.transaction_date >= start,
                        FinanceTransaction.transaction_date <= end,
                    )
                    .order_by(
                        FinanceTransaction.transaction_date,
                        FinanceTransaction.created_at,
                        FinanceTransaction.id,
                    )
                )
            ).all()
        )
        balance, credits, debits = opening, ZERO, ZERO
        items = []
        for row in rows:
            if row.direction == "credit":
                credits += row.amount
                balance += row.amount
            else:
                debits += row.amount
                balance -= row.amount
            item = FinanceTransactionResponse.model_validate(row)
            item.running_balance = self.service._money(balance)
            items.append(item)
        result_account = FinanceAccountResponse.model_validate(account)
        result_account.balance = await self.service.account_balance(account)
        return StatementResponse(
            account=result_account,
            from_date=start,
            to_date=end,
            opening_balance=opening,
            credits=credits,
            debits=debits,
            closing_balance=balance,
            transactions=items,
        )
