"""Transactional voucher workflow and append-only finance operations."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from meetinghq_api.core.errors import AuthorizationError
from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.finance.models import (
    ExpenseCategory,
    FinanceAccount,
    FinanceTransaction,
    Voucher,
    VoucherDisbursement,
    VoucherHistory,
    VoucherLineItem,
    VoucherReview,
    VoucherSequence,
)
from meetinghq_api.modules.finance.schemas import (
    DisbursementInput,
    FinanceAccountInput,
    FinanceAdjustmentInput,
    FinanceTransferInput,
    ReconciliationInput,
    ReversalInput,
    VoucherCreate,
    VoucherReturnInput,
    VoucherReviewInput,
    VoucherUpdate,
)
from meetinghq_api.modules.meetings.models import Meeting, MeetingAttendee
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization, OrganizationUnit
from meetinghq_api.modules.users.models import Permission, Role, User, UserStatus
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
OPEN_EDITABLE = {"draft", "returned"}


class FinanceService:
    """All financial writes share one AsyncSession and commit atomically at request end."""

    def __init__(self, session: AsyncSession, notifications: NotificationService) -> None:
        self.session = session
        self.notifications = notifications
        self.events = TransactionalDomainEventPublisher(session)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _permissions(user: User) -> set[str]:
        return {permission.name for role in user.roles for permission in role.permissions}

    @classmethod
    def _has(cls, user: User, permission: str) -> bool:
        return permission in cls._permissions(user)

    @classmethod
    def require(cls, actor: User, permission: str) -> None:
        if not cls._has(actor, permission):
            raise AuthorizationError(f"Permission required: {permission}")

    def managed_requesters(self, actor: User) -> ColumnElement[bool]:
        return Voucher.requester_id.in_(
            select(User.id).where(
                User.organization_id == actor.organization_id,
                or_(
                    User.manager_id == actor.id,
                    User.department_id.in_(
                        select(OrganizationUnit.id).where(
                            OrganizationUnit.organization_id == actor.organization_id,
                            OrganizationUnit.manager_id == actor.id,
                            OrganizationUnit.deleted_at.is_(None),
                        )
                    ),
                ),
            )
        )

    def visible(self, actor: User) -> ColumnElement[bool]:
        permissions = self._permissions(actor)
        own = Voucher.requester_id == actor.id
        if permissions & {"vouchers.audit", "vouchers.view_all"}:
            return Voucher.organization_id == actor.organization_id
        if permissions & {"vouchers.approve", "vouchers.return", "vouchers.reject"}:
            own = or_(own, and_(self.managed_requesters(actor), Voucher.status != "draft"))
        if "vouchers.disburse" in permissions:
            own = or_(own, Voucher.status.in_({"approved", "partially_disbursed", "completed"}))
        return own

    async def _voucher(self, actor: User, voucher_id: uuid.UUID, *, lock: bool = False) -> Voucher:
        statement = select(Voucher).where(
            Voucher.id == voucher_id,
            Voucher.organization_id == actor.organization_id,
            Voucher.deleted_at.is_(None),
            self.visible(actor),
        )
        if lock:
            statement = statement.with_for_update()
        voucher = await self.session.scalar(statement)
        if voucher is None:
            raise NotFoundError("Voucher not found")
        return voucher

    async def _account(
        self, actor: User, account_id: uuid.UUID, *, lock: bool = False
    ) -> FinanceAccount:
        statement = select(FinanceAccount).where(
            FinanceAccount.id == account_id,
            FinanceAccount.organization_id == actor.organization_id,
            FinanceAccount.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        account = await self.session.scalar(statement)
        if account is None:
            raise NotFoundError("Finance account not found")
        return account

    async def _category(self, actor: User, category_id: uuid.UUID | None) -> None:
        if category_id is None:
            return
        item = await self.session.scalar(
            select(ExpenseCategory).where(
                ExpenseCategory.id == category_id,
                ExpenseCategory.organization_id == actor.organization_id,
                ExpenseCategory.deleted_at.is_(None),
                ExpenseCategory.is_active.is_(True),
            )
        )
        if item is None:
            raise NotFoundError("Expense category not found")

    async def _department(self, actor: User, department_id: uuid.UUID | None) -> None:
        if department_id is None:
            return
        item = await self.session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.id == department_id,
                OrganizationUnit.organization_id == actor.organization_id,
                OrganizationUnit.deleted_at.is_(None),
            )
        )
        if item is None:
            raise NotFoundError("Department not found")

    async def _number(self, organization_id: uuid.UUID) -> str:
        """Allocate VCH-yyyymmdd-0001 under a locked, tenant/day sequence row."""
        today = datetime.now(UTC).date()
        # Lock the existing tenant root first, including the first allocation of a day.
        await self.session.scalar(
            select(Organization.id).where(Organization.id == organization_id).with_for_update()
        )
        row = await self.session.scalar(
            select(VoucherSequence)
            .where(
                VoucherSequence.organization_id == organization_id,
                VoucherSequence.sequence_date == today,
            )
            .with_for_update()
        )
        if row is None:
            row = VoucherSequence(
                organization_id=organization_id, sequence_date=today, next_sequence=1
            )
            self.session.add(row)
            await self.session.flush()
        number = row.next_sequence
        row.next_sequence += 1
        return f"VCH-{today:%Y%m%d}-{number:04d}"

    async def _history(
        self,
        voucher: Voucher,
        actor: User,
        event_type: str,
        reason: str | None = None,
        **payload: object,
    ) -> None:
        self.session.add(
            VoucherHistory(
                organization_id=voucher.organization_id,
                voucher_id=voucher.id,
                actor_id=actor.id,
                event_type=event_type,
                reason=reason,
                payload=payload,
            )
        )
        self.session.add(
            AuditLog(
                organization_id=voucher.organization_id,
                user_id=actor.id,
                action=f"voucher.{event_type}",
                resource="voucher",
                resource_id=voucher.id,
                audit_metadata=payload,
            )
        )
        if event_type in {
            "submitted",
            "approved",
            "returned",
            "rejected",
            "partially_disbursed",
            "disbursed",
            "reversed",
        }:
            await self._notify(voucher, actor, event_type)

    async def _notify(self, voucher: Voucher, actor: User, event_type: str) -> None:
        recipients = {voucher.requester_id}
        if event_type in {"submitted", "approved"}:
            permission = "vouchers.approve" if event_type == "submitted" else "vouchers.disburse"
            users = list(
                (
                    await self.session.scalars(
                        select(User)
                        .where(
                            User.organization_id == actor.organization_id,
                            User.status == UserStatus.ACTIVE,
                            User.roles.any(Role.permissions.any(Permission.name == permission)),
                        )
                        .options(selectinload(User.roles).selectinload(Role.permissions))
                    )
                ).all()
            )
            for candidate in users:
                if candidate.id == voucher.requester_id:
                    continue
                if event_type == "submitted" and not self._has(candidate, "vouchers.view_all"):
                    allowed = await self.session.scalar(
                        select(Voucher.id).where(
                            Voucher.id == voucher.id, self.managed_requesters(candidate)
                        )
                    )
                    if not allowed:
                        continue
                if event_type == "approved" and candidate.id == actor.id:
                    continue
                recipients.add(candidate.id)
        for recipient in recipients - {actor.id}:
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=recipient,
                notification_type=f"voucher_{event_type}",
                title=f"{voucher.voucher_number}: {event_type.replace('_', ' ')}",
                body=voucher.title,
                category="approvals",
                metadata={"voucher_id": str(voucher.id)},
                action_url=f"/vouchers/{voucher.id}",
            )

    async def _meeting(self, actor: User, meeting_id: uuid.UUID | None) -> None:
        if meeting_id is None:
            return
        self.require(actor, "meetings.read")
        query = select(Meeting.id).where(
            Meeting.id == meeting_id, Meeting.organization_id == actor.organization_id
        )
        if not self._has(actor, "meetings.manage"):
            query = query.where(
                or_(
                    Meeting.organizer_id == actor.id,
                    Meeting.id.in_(
                        select(MeetingAttendee.meeting_id).where(
                            MeetingAttendee.user_id == actor.id
                        )
                    ),
                )
            )
        if await self.session.scalar(query) is None:
            raise NotFoundError("Meeting not found")

    async def _replace_lines(self, actor: User, voucher: Voucher, body: VoucherCreate) -> None:
        await self._category(actor, body.expense_category_id)
        await self._department(actor, body.department_id)
        await self.session.execute(
            delete(VoucherLineItem).where(
                VoucherLineItem.voucher_id == voucher.id,
                VoucherLineItem.organization_id == actor.organization_id,
            )
        )
        total = ZERO
        for position, line in enumerate(body.line_items):
            await self._category(actor, line.expense_category_id)
            amount = self._money(line.quantity * line.unit_price + line.tax_amount)
            total += amount
            self.session.add(
                VoucherLineItem(
                    organization_id=actor.organization_id,
                    voucher_id=voucher.id,
                    expense_category_id=line.expense_category_id,
                    description=line.description.strip(),
                    quantity=line.quantity,
                    unit_price=self._money(line.unit_price),
                    tax_amount=self._money(line.tax_amount),
                    amount=amount,
                    notes=line.notes,
                    position=position,
                )
            )
        voucher.requested_amount = self._money(total)
        if total > Decimal("9999999999999999.99"):
            raise ValidationError("Voucher total exceeds supported amount")

    async def create(self, actor: User, body: VoucherCreate) -> Voucher:
        self.require(actor, "vouchers.create")
        await self._meeting(actor, body.meeting_id)
        voucher = Voucher(
            organization_id=actor.organization_id,
            voucher_number=await self._number(actor.organization_id),
            requester_id=actor.id,
            department_id=body.department_id or actor.department_id,
            expense_category_id=body.expense_category_id,
            meeting_id=body.meeting_id,
            title=body.title.strip(),
            description=body.description,
            currency=body.currency,
        )
        self.session.add(voucher)
        await self.session.flush()
        await self._replace_lines(actor, voucher, body)
        await self._history(voucher, actor, "created")
        return voucher

    async def update_draft(
        self, actor: User, voucher_id: uuid.UUID, body: VoucherUpdate
    ) -> Voucher:
        self.require(actor, "vouchers.edit_draft")
        voucher = await self._voucher(actor, voucher_id, lock=True)
        if voucher.requester_id != actor.id or voucher.status not in OPEN_EDITABLE:
            raise AuthorizationError("Only the requester may edit a draft or returned voucher")
        changes = body.model_dump(exclude_unset=True, exclude={"line_items"})
        if "department_id" in changes:
            await self._department(actor, body.department_id)
        if "expense_category_id" in changes:
            await self._category(actor, body.expense_category_id)
        if "meeting_id" in changes:
            await self._meeting(actor, body.meeting_id)
        for name, value in changes.items():
            setattr(voucher, name, value)
        if body.line_items is not None:
            await self._replace_lines(
                actor,
                voucher,
                VoucherCreate(
                    title=voucher.title,
                    department_id=voucher.department_id,
                    expense_category_id=voucher.expense_category_id,
                    line_items=body.line_items,
                ),
            )
        await self._history(voucher, actor, "edited")
        return voucher

    async def submit(self, actor: User, voucher_id: uuid.UUID) -> Voucher:
        self.require(actor, "vouchers.submit")
        voucher = await self._voucher(actor, voucher_id, lock=True)
        if voucher.requester_id != actor.id or voucher.status not in OPEN_EDITABLE:
            raise AuthorizationError("Only the requester may submit a draft or returned voucher")
        if voucher.requested_amount <= ZERO:
            raise ValidationError("Add at least one positive line item before submitting")
        voucher.status = "submitted"
        voucher.submitted_at = datetime.now(UTC)
        await self._history(voucher, actor, "submitted")
        return voucher

    async def review(
        self,
        actor: User,
        voucher_id: uuid.UUID,
        decision: str,
        body: VoucherReviewInput | VoucherReturnInput,
    ) -> Voucher:
        permission = {"approved": "approve", "returned": "return", "rejected": "reject"}.get(
            decision
        )
        if permission is None:
            raise ValidationError("Unsupported voucher decision")
        self.require(actor, f"vouchers.{permission}")
        voucher = await self._voucher(actor, voucher_id, lock=True)
        if not self._has(actor, "vouchers.view_all") and not await self.session.scalar(
            select(Voucher.id).where(Voucher.id == voucher.id, self.managed_requesters(actor))
        ):
            raise AuthorizationError("Only an authorized reporting-line reviewer may review")
        if voucher.status != "submitted":
            raise ConflictError("Only submitted vouchers may be reviewed")
        if voucher.requester_id == actor.id:
            raise AuthorizationError("A requester cannot review their own voucher")
        comment = body.comment
        approved = body.approved_amount if isinstance(body, VoucherReviewInput) else None
        if decision in {"returned", "rejected"} and not comment:
            raise ValidationError("A return or rejection reason is required")
        if decision == "approved":
            approved = self._money(approved if approved is not None else voucher.requested_amount)
            if approved <= ZERO or approved > voucher.requested_amount:
                raise ValidationError(
                    "Approved amount must be positive and cannot exceed the requested amount"
                )
            voucher.status, voucher.approved_at, voucher.approved_amount = (
                "approved",
                datetime.now(UTC),
                approved,
            )
        elif decision == "returned":
            voucher.status, voucher.returned_at = "returned", datetime.now(UTC)
        elif decision == "rejected":
            voucher.status, voucher.rejected_at = "rejected", datetime.now(UTC)
        else:
            raise ValidationError("Unsupported voucher decision")
        self.session.add(
            VoucherReview(
                organization_id=actor.organization_id,
                voucher_id=voucher.id,
                reviewer_id=actor.id,
                decision=decision,
                approved_amount=approved,
                comment=comment,
            )
        )
        await self._history(
            voucher,
            actor,
            decision,
            comment,
            approved_amount=str(approved) if approved is not None else None,
        )
        return voucher

    async def disburse(
        self, actor: User, voucher_id: uuid.UUID, body: DisbursementInput
    ) -> Voucher:
        self.require(actor, "vouchers.disburse")
        voucher = await self._voucher(actor, voucher_id, lock=True)
        if voucher.requester_id == actor.id:
            raise AuthorizationError("A requester cannot disburse their own voucher")
        review = await self.session.scalar(
            select(VoucherReview)
            .where(
                VoucherReview.voucher_id == voucher.id,
                VoucherReview.organization_id == actor.organization_id,
                VoucherReview.decision == "approved",
            )
            .order_by(VoucherReview.created_at.desc())
        )
        if review and review.reviewer_id == actor.id:
            raise AuthorizationError("The approving reviewer cannot disburse this voucher")
        existing = await self.session.scalar(
            select(VoucherDisbursement).where(
                VoucherDisbursement.organization_id == actor.organization_id,
                VoucherDisbursement.idempotency_key == body.idempotency_key,
            )
        )
        if existing:
            if (
                existing.voucher_id != voucher.id
                or existing.disbursed_by_id != actor.id
                or any(
                    getattr(existing, name) != getattr(body, name)
                    for name in (
                        "account_id",
                        "amount",
                        "payment_method",
                        "payment_reference",
                        "beneficiary",
                        "note",
                        "payment_date",
                    )
                )
            ):
                raise ConflictError("Idempotency key belongs to a different payment request")
            return voucher
        if voucher.status not in {"approved", "partially_disbursed"}:
            raise ConflictError("Only approved vouchers can be disbursed")
        if await self.session.scalar(
            select(FinanceTransaction.id).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.idempotency_key == body.idempotency_key,
            )
        ):
            raise ConflictError("Idempotency key already used")
        account = await self._account(actor, body.account_id, lock=True)
        if account.status != "active" or account.currency != voucher.currency:
            raise ValidationError("Use an active account with the voucher currency")
        amount = self._money(body.amount)
        outstanding = self._money(voucher.approved_amount - voucher.disbursed_amount)
        if amount > outstanding:
            raise ValidationError("Disbursement cannot exceed the outstanding approved amount")
        reference = f"VCH-DISB-{voucher.voucher_number}-{uuid.uuid4().hex[:8].upper()}"
        transaction = FinanceTransaction(
            organization_id=actor.organization_id,
            account_id=account.id,
            voucher_id=voucher.id,
            reference=reference,
            idempotency_key=body.idempotency_key,
            transaction_type="voucher_disbursement",
            direction="debit",
            amount=amount,
            currency=voucher.currency,
            transaction_date=body.payment_date,
            description=f"Voucher {voucher.voucher_number}: {voucher.title}",
            payment_method=body.payment_method,
            payment_reference=body.payment_reference,
            beneficiary=body.beneficiary,
            created_by_id=actor.id,
        )
        self.session.add(transaction)
        await self.session.flush()
        self.session.add(
            VoucherDisbursement(
                organization_id=actor.organization_id,
                voucher_id=voucher.id,
                account_id=account.id,
                transaction_id=transaction.id,
                amount=amount,
                currency=voucher.currency,
                payment_method=body.payment_method,
                payment_reference=body.payment_reference,
                beneficiary=body.beneficiary,
                note=body.note,
                payment_date=body.payment_date,
                idempotency_key=body.idempotency_key,
                disbursed_by_id=actor.id,
            )
        )
        voucher.disbursed_amount = self._money(voucher.disbursed_amount + amount)
        voucher.status = (
            "completed"
            if voucher.disbursed_amount == voucher.approved_amount
            else "partially_disbursed"
        )
        if voucher.status == "completed":
            voucher.completed_at = datetime.now(UTC)
        await self._history(
            voucher,
            actor,
            "disbursed" if voucher.status == "completed" else "partially_disbursed",
            amount=str(amount),
            reference=reference,
        )
        return voucher

    async def create_account(self, actor: User, body: FinanceAccountInput) -> FinanceAccount:
        self.require(actor, "finance.accounts.manage")
        masked = None
        if body.account_number:
            masked = f"••••{body.account_number[-4:]}" if len(body.account_number) > 4 else "••••"
        account = FinanceAccount(
            organization_id=actor.organization_id,
            account_name=body.account_name.strip(),
            account_code=body.account_code.upper(),
            account_type=body.account_type,
            bank_name=body.bank_name,
            account_number_masked=masked,
            currency=body.currency,
            opening_balance=self._money(body.opening_balance),
            status=body.status,
            description=body.description,
        )
        self.session.add(account)
        await self.session.flush()
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action="finance.account_created",
                resource="finance_account",
                resource_id=account.id,
                audit_metadata={"account_code": account.account_code},
            )
        )
        return account

    async def adjust(self, actor: User, body: FinanceAdjustmentInput) -> FinanceTransaction:
        """Record an explicit, immutable ledger adjustment under finance-admin control."""
        self.require(actor, "finance.transactions.manage")
        account = await self._account(actor, body.account_id, lock=True)
        if account.status != "active":
            raise ValidationError("Use an active finance account")
        existing = await self.session.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.idempotency_key == body.idempotency_key,
            )
        )
        if existing:
            expected_reference = body.reference or existing.reference
            if (
                existing.account_id != account.id
                or existing.direction != body.direction
                or existing.amount != self._money(body.amount)
                or existing.transaction_date != body.transaction_date
                or existing.description != body.description.strip()
                or existing.reference != expected_reference
                or existing.transaction_type != "adjustment"
            ):
                raise ConflictError("Idempotency key belongs to a different ledger adjustment")
            return existing
        reference = body.reference or f"ADJ-{uuid.uuid4().hex[:12].upper()}"
        transaction = FinanceTransaction(
            organization_id=actor.organization_id,
            account_id=account.id,
            reference=reference,
            idempotency_key=body.idempotency_key,
            transaction_type="adjustment",
            direction=body.direction,
            amount=self._money(body.amount),
            currency=account.currency,
            transaction_date=body.transaction_date,
            description=body.description.strip(),
            created_by_id=actor.id,
        )
        self.session.add(transaction)
        await self.session.flush()
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action="finance.adjustment_created",
                resource="finance_transaction",
                resource_id=transaction.id,
                audit_metadata={"account_id": str(account.id), "direction": body.direction},
            )
        )
        return transaction

    async def transfer(
        self, actor: User, body: FinanceTransferInput
    ) -> tuple[FinanceTransaction, FinanceTransaction]:
        """Create the debit and credit legs together; no partial transfer can commit."""
        self.require(actor, "finance.transactions.manage")
        if body.source_account_id == body.destination_account_id:
            raise ValidationError("Source and destination accounts must be different")
        account_ids = sorted((body.source_account_id, body.destination_account_id), key=str)
        accounts = {
            account.id: account
            for account in (
                await self.session.scalars(
                    select(FinanceAccount)
                    .where(
                        FinanceAccount.organization_id == actor.organization_id,
                        FinanceAccount.id.in_(account_ids),
                        FinanceAccount.deleted_at.is_(None),
                    )
                    .order_by(FinanceAccount.id)
                    .with_for_update()
                )
            ).all()
        }
        source = accounts.get(body.source_account_id)
        destination = accounts.get(body.destination_account_id)
        if source is None or destination is None:
            raise NotFoundError("Finance account not found")
        if source.status != "active" or destination.status != "active":
            raise ValidationError("Transfers require active finance accounts")
        if source.currency != destination.currency:
            raise ValidationError("Transfers require matching account currencies")
        debit_key, credit_key = f"{body.idempotency_key}:debit", f"{body.idempotency_key}:credit"
        existing = list(
            (
                await self.session.scalars(
                    select(FinanceTransaction).where(
                        FinanceTransaction.organization_id == actor.organization_id,
                        FinanceTransaction.idempotency_key.in_((debit_key, credit_key)),
                    )
                )
            ).all()
        )
        if existing:
            if len(existing) != 2:
                raise ConflictError("Incomplete transfer idempotency record detected")
            by_direction = {entry.direction: entry for entry in existing}
            debit, credit = by_direction.get("debit"), by_direction.get("credit")
            if (
                debit is None
                or credit is None
                or (
                    debit.account_id != source.id
                    or credit.account_id != destination.id
                    or debit.amount != self._money(body.amount)
                    or credit.amount != self._money(body.amount)
                    or debit.transaction_date != body.transaction_date
                    or credit.transaction_date != body.transaction_date
                    or debit.transaction_type != "transfer"
                    or credit.transaction_type != "transfer"
                    or debit.transfer_group_id != credit.transfer_group_id
                )
            ):
                raise ConflictError("Idempotency key belongs to a different transfer")
            return debit, credit
        transfer_group_id = uuid.uuid4()
        reference = body.reference or f"XFR-{uuid.uuid4().hex[:12].upper()}"
        amount = self._money(body.amount)
        common = {
            "organization_id": actor.organization_id,
            "transfer_group_id": transfer_group_id,
            "transaction_type": "transfer",
            "amount": amount,
            "currency": source.currency,
            "transaction_date": body.transaction_date,
            "description": body.description.strip(),
            "created_by_id": actor.id,
        }
        debit = FinanceTransaction(
            **common,
            account_id=source.id,
            reference=f"{reference}-OUT",
            idempotency_key=debit_key,
            direction="debit",
        )
        credit = FinanceTransaction(
            **common,
            account_id=destination.id,
            reference=f"{reference}-IN",
            idempotency_key=credit_key,
            direction="credit",
        )
        self.session.add_all((debit, credit))
        await self.session.flush()
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action="finance.transfer_created",
                resource="finance_transfer",
                resource_id=transfer_group_id,
                audit_metadata={
                    "source_account_id": str(source.id),
                    "destination_account_id": str(destination.id),
                    "amount": str(amount),
                },
            )
        )
        return debit, credit

    async def reverse(
        self, actor: User, transaction_id: uuid.UUID, body: ReversalInput
    ) -> FinanceTransaction:
        self.require(actor, "finance.reverse")
        original = await self.session.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.id == transaction_id,
                FinanceTransaction.organization_id == actor.organization_id,
            )
        )
        if original is None:
            raise NotFoundError("Finance transaction not found")
        voucher = None
        if original.voucher_id:
            voucher = await self._voucher(actor, original.voucher_id, lock=True)
        await self._account(actor, original.account_id, lock=True)
        duplicate = await self.session.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.idempotency_key == body.idempotency_key,
            )
        )
        if duplicate:
            if (
                duplicate.reversal_of_id != original.id
                or duplicate.description != body.reason
                or duplicate.created_by_id != actor.id
            ):
                raise ConflictError("Idempotency key belongs to another request")
            return duplicate
        if original.reversal_of_id is not None:
            raise ConflictError("A reversal cannot itself be reversed")
        existing = await self.session.scalar(
            select(FinanceTransaction.id).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.reversal_of_id == original.id,
            )
        )
        if existing:
            raise ConflictError("This transaction has already been reversed")
        direction = "credit" if original.direction == "debit" else "debit"
        reversal = FinanceTransaction(
            organization_id=actor.organization_id,
            account_id=original.account_id,
            voucher_id=original.voucher_id,
            reversal_of_id=original.id,
            reference=f"REV-{original.reference}",
            idempotency_key=body.idempotency_key,
            transaction_type="reversal",
            direction=direction,
            amount=original.amount,
            currency=original.currency,
            transaction_date=date.today(),
            description=body.reason,
            payment_method=original.payment_method,
            payment_reference=original.payment_reference,
            beneficiary=original.beneficiary,
            created_by_id=actor.id,
        )
        self.session.add(reversal)
        await self.session.flush()
        if voucher:
            voucher.disbursed_amount = self._money(voucher.disbursed_amount - original.amount)
            voucher.status = "partially_disbursed" if voucher.disbursed_amount else "approved"
            voucher.completed_at = None
            await self._history(
                voucher,
                actor,
                "reversed",
                body.reason,
                reference=reversal.reference,
                amount=str(original.amount),
            )
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action="finance.transaction_reversed",
                resource="finance_transaction",
                resource_id=original.id,
                audit_metadata={"reversal_id": str(reversal.id)},
            )
        )
        return reversal

    async def reconcile(
        self, actor: User, transaction_id: uuid.UUID, body: ReconciliationInput
    ) -> FinanceTransaction:
        self.require(actor, "finance.reconcile")
        transaction = await self.session.scalar(
            select(FinanceTransaction)
            .where(
                FinanceTransaction.id == transaction_id,
                FinanceTransaction.organization_id == actor.organization_id,
            )
            .with_for_update()
        )
        if transaction is None:
            raise NotFoundError("Finance transaction not found")
        transaction.reconciled, transaction.reconciled_at = True, datetime.now(UTC)
        transaction.reconciliation_reference, transaction.reconciliation_note = (
            body.reference,
            body.note,
        )
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action="finance.transaction_reconciled",
                resource="finance_transaction",
                resource_id=transaction.id,
                audit_metadata={"reference": body.reference},
            )
        )
        return transaction

    async def account_balance(self, account: FinanceAccount) -> Decimal:
        credit = await self.session.scalar(
            select(func.coalesce(func.sum(FinanceTransaction.amount), ZERO)).where(
                FinanceTransaction.account_id == account.id,
                FinanceTransaction.organization_id == account.organization_id,
                FinanceTransaction.direction == "credit",
            )
        )
        debit = await self.session.scalar(
            select(func.coalesce(func.sum(FinanceTransaction.amount), ZERO)).where(
                FinanceTransaction.account_id == account.id,
                FinanceTransaction.direction == "debit",
                FinanceTransaction.organization_id == account.organization_id,
            )
        )
        return self._money(
            account.opening_balance + Decimal(credit or ZERO) - Decimal(debit or ZERO)
        )
