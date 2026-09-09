"""Tenant-isolated Leave Management application service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import structlog
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.calendar.models import (
    Calendar,
    CalendarEvent,
    CalendarType,
    EventStatus,
    Holiday,
    Visibility,
)
from meetinghq_api.modules.leave.models import (
    LeaveAttachment,
    LeaveBalanceLedgerEntry,
    LeaveEntitlement,
    LeavePeriod,
    LeaveRequest,
    LeaveRequestHistory,
    LeaveType,
)
from meetinghq_api.modules.leave.schemas import (
    AdjustmentInput,
    AdjustmentResponse,
    BalanceListItem,
    BalancePage,
    BalanceResponse,
    ControlledAdjustmentInput,
    EntitlementInput,
    LeaveAttachmentResponse,
    LeaveAvailabilityItem,
    LeaveHistoryResponse,
    LeavePeriodInput,
    LeaveReportRow,
    LeaveRequestDetail,
    LeaveRequestInput,
    LeaveRequestPage,
    LeaveRequestResponse,
    LeaveStatusSummary,
    LeaveSummaryResponse,
    LeaveTypeInput,
    LedgerEntryResponse,
    LedgerPage,
    ManagerLeaveSummary,
    WorkingDayResult,
    WorkingWeekInput,
    WorkingWeekResponse,
)
from meetinghq_api.modules.notifications.email_templates import (
    EmailTemplateRegistry,
    LeaveEmailData,
    TemplateKey,
)
from meetinghq_api.modules.notifications.service import MeetingEmailSender, NotificationService
from meetinghq_api.modules.organizations.models import Organization, OrganizationUnit
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.shared.exceptions import AuthorizationError, NotFoundError, ValidationError

logger = structlog.get_logger(__name__)


class LeaveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_scheduled_policies(self, effective_date: date | None = None) -> int:
        """Run tenant-isolated policy maintenance through the shared worker."""
        when = effective_date or date.today()
        processed = 0
        organizations = list((await self.session.scalars(select(Organization))).all())
        for organization in organizations:
            actor = await self.session.scalar(
                select(User)
                .where(
                    User.organization_id == organization.id,
                    User.status == UserStatus.ACTIVE,
                    User.employment_status != "terminated",
                )
                .order_by(User.created_at)
                .limit(1)
            )
            if actor is None:
                continue
            try:
                tenant_processed = 0
                async with self.session.begin_nested():
                    tenant_processed += await self.process_accruals(actor, when)
                    current = await self.session.scalar(
                        select(LeavePeriod)
                        .where(
                            LeavePeriod.organization_id == organization.id,
                            LeavePeriod.status == "open",
                            LeavePeriod.start_date <= when,
                            LeavePeriod.end_date >= when,
                        )
                        .order_by(LeavePeriod.start_date.desc())
                        .limit(1)
                    )
                    previous = None
                    if current is not None:
                        previous = await self.session.scalar(
                            select(LeavePeriod)
                            .where(
                                LeavePeriod.organization_id == organization.id,
                                LeavePeriod.end_date < current.start_date,
                            )
                            .order_by(LeavePeriod.end_date.desc())
                            .limit(1)
                        )
                    if current is not None and previous is not None:
                        tenant_processed += await self.process_carryover(
                            actor, previous.id, current.id, when
                        )
                    tenant_processed += await self.process_expiry(actor, when)
                processed += tenant_processed
            except Exception:
                # Each tenant is isolated; a malformed policy cannot halt others.
                await logger.aexception(
                    "leave_policy_tenant_processing_failed", organization_id=str(organization.id)
                )
                continue
        return processed

    @staticmethod
    def permissions(user: User) -> set[str]:
        return {p.name for role in user.roles for p in role.permissions}

    def _manage(self, user: User) -> bool:
        return bool({"leave.balances.adjust", "admin.manage"} & self.permissions(user))

    async def _can_review(self, actor: User, request: LeaveRequest) -> bool:
        """Administrators review broadly; managers are restricted to direct reports."""
        if self._manage(actor):
            return True
        if request.employee_id == actor.id:
            return False
        employee = await self._employee(actor, request.employee_id)
        return employee.manager_id == actor.id and bool(
            {"leave.review", "leave.approve", "leave.reject"} & self.permissions(actor)
        )

    def _audit(
        self,
        user: User,
        action: str,
        resource_id: uuid.UUID,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=user.organization_id,
                user_id=user.id,
                action=action,
                resource="leave",
                resource_id=resource_id,
                audit_metadata=metadata or {},
            )
        )

    async def _type(self, user: User, type_id: uuid.UUID, active: bool = False) -> LeaveType:
        statement = select(LeaveType).where(
            LeaveType.id == type_id,
            LeaveType.organization_id == user.organization_id,
            LeaveType.deleted_at.is_(None),
        )
        if active:
            statement = statement.where(LeaveType.is_active.is_(True))
        item = await self.session.scalar(statement)
        if item is None:
            raise NotFoundError("Leave type not found")
        return item

    async def _period(
        self, user: User, *, period_id: uuid.UUID | None = None, on_date: date | None = None
    ) -> LeavePeriod:
        statement = select(LeavePeriod).where(LeavePeriod.organization_id == user.organization_id)
        if period_id:
            statement = statement.where(LeavePeriod.id == period_id)
        elif on_date:
            statement = statement.where(
                LeavePeriod.status == "open",
                LeavePeriod.start_date <= on_date,
                LeavePeriod.end_date >= on_date,
            )
        item = await self.session.scalar(statement)
        if item is None:
            raise NotFoundError("Active leave period not found")
        return item

    async def _employee(self, actor: User, employee_id: uuid.UUID) -> User:
        item = await self.session.scalar(
            select(User).where(
                User.id == employee_id,
                User.organization_id == actor.organization_id,
                User.removed_at.is_(None),
            )
        )
        if item is None:
            raise NotFoundError("Employee not found")
        return item

    async def list_types(
        self, user: User, *, search: str | None = None, active: bool | None = None
    ) -> list[LeaveType]:
        query = select(LeaveType).where(
            LeaveType.organization_id == user.organization_id,
            LeaveType.deleted_at.is_(None),
        )
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(LeaveType.name.ilike(term), LeaveType.code.ilike(term)))
        if active is not None:
            query = query.where(LeaveType.is_active.is_(active))
        return list((await self.session.scalars(query.order_by(LeaveType.name))).all())

    async def set_type_active(self, user: User, type_id: uuid.UUID, active: bool) -> LeaveType:
        item = await self._type(user, type_id)
        item.is_active = active
        self._audit(user, "leave.type.activated" if active else "leave.type.deactivated", item.id)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def create_type(self, user: User, body: LeaveTypeInput) -> LeaveType:
        code = body.code.upper()
        if await self.session.scalar(
            select(LeaveType.id).where(
                LeaveType.organization_id == user.organization_id,
                LeaveType.code == code,
                LeaveType.deleted_at.is_(None),
            )
        ):
            raise ValidationError("A leave type with this code already exists")
        item = LeaveType(
            organization_id=user.organization_id,
            **body.model_dump(exclude={"code", "eligible_employment_types"}),
            code=code,
            eligible_employment_types=",".join(body.eligible_employment_types) or None,
        )
        self.session.add(item)
        await self.session.flush()
        self._audit(user, "leave.type.created", item.id)
        return item

    async def update_type(self, user: User, type_id: uuid.UUID, body: LeaveTypeInput) -> LeaveType:
        item = await self._type(user, type_id)
        duplicate = await self.session.scalar(
            select(LeaveType.id).where(
                LeaveType.organization_id == user.organization_id,
                LeaveType.code == body.code.upper(),
                LeaveType.id != item.id,
                LeaveType.deleted_at.is_(None),
            )
        )
        if duplicate:
            raise ValidationError("A leave type with this code already exists")
        for field, value in body.model_dump(exclude={"eligible_employment_types"}).items():
            setattr(item, field, value)
        item.code = body.code.upper()
        item.eligible_employment_types = ",".join(body.eligible_employment_types) or None
        self._audit(user, "leave.type.updated", item.id)
        return item

    async def list_periods(self, user: User) -> list[LeavePeriod]:
        return list(
            (
                await self.session.scalars(
                    select(LeavePeriod)
                    .where(LeavePeriod.organization_id == user.organization_id)
                    .order_by(LeavePeriod.start_date.desc())
                )
            ).all()
        )

    async def create_period(self, user: User, body: LeavePeriodInput) -> LeavePeriod:
        if await self.session.scalar(
            select(LeavePeriod.id).where(
                LeavePeriod.organization_id == user.organization_id,
                func.lower(LeavePeriod.name) == body.name.lower(),
            )
        ):
            raise ValidationError("A leave period with this name already exists")
        if await self.session.scalar(
            select(LeavePeriod.id).where(
                LeavePeriod.organization_id == user.organization_id,
                LeavePeriod.status == "open",
                LeavePeriod.start_date <= body.end_date,
                LeavePeriod.end_date >= body.start_date,
            )
        ):
            raise ValidationError("An open leave period already overlaps these dates")
        item = LeavePeriod(organization_id=user.organization_id, **body.model_dump())
        self.session.add(item)
        await self.session.flush()
        self._audit(user, "leave.period.created", item.id)
        return item

    async def current_period(self, user: User, on_date: date | None = None) -> LeavePeriod:
        return await self._period(user, on_date=on_date or date.today())

    async def period_detail(self, user: User, period_id: uuid.UUID) -> LeavePeriod:
        return await self._period(user, period_id=period_id)

    async def set_period_status(self, user: User, period_id: uuid.UUID, status: str) -> LeavePeriod:
        item = await self._period(user, period_id=period_id)
        if item.status == status:
            return item
        if status == "open":
            overlap = await self.session.scalar(
                select(LeavePeriod.id).where(
                    LeavePeriod.organization_id == user.organization_id,
                    LeavePeriod.id != item.id,
                    LeavePeriod.status == "open",
                    LeavePeriod.start_date <= item.end_date,
                    LeavePeriod.end_date >= item.start_date,
                )
            )
            if overlap:
                raise ValidationError("This period overlaps an existing open leave period")
        item.status = status
        self._audit(user, f"leave.period.{status}", item.id)
        await self.session.flush()
        return item

    async def entitlement(self, user: User, body: EntitlementInput) -> LeaveEntitlement:
        await self._employee(user, body.employee_id)
        await self._type(user, body.leave_type_id)
        await self._period(user, period_id=body.leave_period_id)
        if await self.session.scalar(
            select(LeaveEntitlement.id).where(
                LeaveEntitlement.organization_id == user.organization_id,
                LeaveEntitlement.employee_id == body.employee_id,
                LeaveEntitlement.leave_type_id == body.leave_type_id,
                LeaveEntitlement.leave_period_id == body.leave_period_id,
            )
        ):
            raise ValidationError(
                "Employee already has an entitlement for this leave type and period"
            )
        item = LeaveEntitlement(
            organization_id=user.organization_id, **body.model_dump(exclude={"reason"})
        )
        self.session.add(item)
        await self.session.flush()
        if body.allocated_days:
            await self._ledger(
                user, item, "allocation", body.allocated_days, date.today(), body.reason
            )
        self._audit(user, "leave.entitlement.created", item.id)
        return item

    async def _ledger(
        self,
        actor: User,
        entitlement: LeaveEntitlement,
        entry_type: str,
        amount: Decimal,
        effective: date,
        reason: str | None,
        reference_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> LeaveBalanceLedgerEntry | None:
        if idempotency_key and await self.session.scalar(
            select(LeaveBalanceLedgerEntry.id).where(
                LeaveBalanceLedgerEntry.organization_id == actor.organization_id,
                LeaveBalanceLedgerEntry.idempotency_key == idempotency_key,
            )
        ):
            return None
        entry = LeaveBalanceLedgerEntry(
            organization_id=actor.organization_id,
            entitlement_id=entitlement.id,
            employee_id=entitlement.employee_id,
            leave_type_id=entitlement.leave_type_id,
            leave_period_id=entitlement.leave_period_id,
            entry_type=entry_type,
            amount=amount,
            effective_date=effective,
            reason=reason,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            actor_id=actor.id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def process_accruals(self, actor: User, effective_date: date) -> int:
        """Apply a single policy cycle; stable keys make retried worker runs safe."""
        entitlements = (
            await self.session.execute(
                select(LeaveEntitlement, LeaveType)
                .join(LeaveType, LeaveType.id == LeaveEntitlement.leave_type_id)
                .where(
                    LeaveEntitlement.organization_id == actor.organization_id,
                    LeaveType.organization_id == actor.organization_id,
                    LeaveType.is_active.is_(True),
                    LeaveType.deleted_at.is_(None),
                )
            )
        ).all()
        count = 0
        for entitlement, leave_type in entitlements:
            if not leave_type.accrual_enabled or not leave_type.default_entitlement:
                continue
            cycle = (
                effective_date.strftime("%Y-%m")
                if leave_type.accrual_frequency == "monthly"
                else (
                    effective_date.strftime("%Y-Q") + str((effective_date.month - 1) // 3 + 1)
                    if leave_type.accrual_frequency == "quarterly"
                    else str(effective_date.year)
                )
            )
            key = f"accrual:{entitlement.id}:{cycle}"
            exists = await self.session.scalar(
                select(LeaveBalanceLedgerEntry.id).where(
                    LeaveBalanceLedgerEntry.organization_id == actor.organization_id,
                    LeaveBalanceLedgerEntry.idempotency_key == key,
                )
            )
            if exists:
                continue
            divisor = {"monthly": Decimal("12"), "quarterly": Decimal("4")}.get(
                leave_type.accrual_frequency or "", Decimal("1")
            )
            await self._ledger(
                actor,
                entitlement,
                "accrual",
                leave_type.default_entitlement / divisor,
                effective_date,
                "Policy accrual",
                idempotency_key=key,
            )
            self._audit(actor, "leave.accrual", entitlement.id, {"cycle": cycle})
            count += 1
        return count

    async def process_carryover(
        self,
        actor: User,
        source_period_id: uuid.UUID,
        destination_period_id: uuid.UUID,
        effective_date: date,
    ) -> int:
        """Copy capped unused balances forward without modifying the source period."""
        source = await self._period(actor, period_id=source_period_id)
        destination = await self._period(actor, period_id=destination_period_id)
        if destination.start_date <= source.end_date:
            raise ValidationError("Carryover destination must follow the source period")
        rows = list(
            (
                await self.session.scalars(
                    select(LeaveEntitlement).where(
                        LeaveEntitlement.organization_id == actor.organization_id,
                        LeaveEntitlement.leave_period_id == source.id,
                    )
                )
            ).all()
        )
        created = 0
        for entitlement in rows:
            leave_type = await self._type(actor, entitlement.leave_type_id)
            if not leave_type.carryover_enabled or not leave_type.carryover_limit:
                continue
            target = await self.session.scalar(
                select(LeaveEntitlement).where(
                    LeaveEntitlement.organization_id == actor.organization_id,
                    LeaveEntitlement.employee_id == entitlement.employee_id,
                    LeaveEntitlement.leave_type_id == entitlement.leave_type_id,
                    LeaveEntitlement.leave_period_id == destination.id,
                )
            )
            if target is None:
                target = LeaveEntitlement(
                    organization_id=actor.organization_id,
                    employee_id=entitlement.employee_id,
                    leave_type_id=entitlement.leave_type_id,
                    leave_period_id=destination.id,
                    allocated_days=Decimal("0"),
                )
                self.session.add(target)
                await self.session.flush()
            available = (await self.balance(actor, entitlement.id)).available
            amount = min(max(available, Decimal("0")), leave_type.carryover_limit)
            key = f"carryover:{entitlement.id}:{destination.id}"
            if amount and not await self.session.scalar(
                select(LeaveBalanceLedgerEntry.id).where(
                    LeaveBalanceLedgerEntry.organization_id == actor.organization_id,
                    LeaveBalanceLedgerEntry.idempotency_key == key,
                )
            ):
                await self._ledger(
                    actor,
                    target,
                    "carryover",
                    amount,
                    effective_date,
                    f"Carryover from {source.name}",
                    entitlement.id,
                    key,
                )
                self._audit(
                    actor,
                    "leave.carryover",
                    target.id,
                    {"source_entitlement_id": str(entitlement.id)},
                )
                created += 1
        return created

    async def process_expiry(self, actor: User, effective_date: date) -> int:
        """Expire only carry-forward entries whose policy expiry date has arrived."""
        rows = list(
            (
                await self.session.scalars(
                    select(LeaveBalanceLedgerEntry).where(
                        LeaveBalanceLedgerEntry.organization_id == actor.organization_id,
                        LeaveBalanceLedgerEntry.entry_type == "carryover",
                    )
                )
            ).all()
        )
        expired = 0
        for row in rows:
            leave_type = await self._type(actor, row.leave_type_id)
            if not leave_type.carryover_expiry_months:
                continue
            expiry = row.effective_date + timedelta(days=30 * leave_type.carryover_expiry_months)
            key = f"expiry:{row.id}:{expiry.isoformat()}"
            if expiry <= effective_date and not await self.session.scalar(
                select(LeaveBalanceLedgerEntry.id).where(
                    LeaveBalanceLedgerEntry.organization_id == actor.organization_id,
                    LeaveBalanceLedgerEntry.idempotency_key == key,
                )
            ):
                entitlement = await self.session.get(LeaveEntitlement, row.entitlement_id)
                if entitlement:
                    await self._ledger(
                        actor,
                        entitlement,
                        "expiry",
                        -row.amount,
                        effective_date,
                        "Carryover expiry",
                        row.id,
                        key,
                    )
                    self._audit(
                        actor, "leave.expiry", entitlement.id, {"source_ledger_id": str(row.id)}
                    )
                    expired += 1
        return expired

    async def balance(self, user: User, entitlement_id: uuid.UUID) -> BalanceResponse:
        item = await self.session.scalar(
            select(LeaveEntitlement).where(
                LeaveEntitlement.id == entitlement_id,
                LeaveEntitlement.organization_id == user.organization_id,
            )
        )
        if item is None:
            raise NotFoundError("Leave entitlement not found")
        if item.employee_id != user.id and not self._manage(user):
            raise AuthorizationError("You cannot view this balance")
        rows = list(
            (
                await self.session.scalars(
                    select(LeaveBalanceLedgerEntry).where(
                        LeaveBalanceLedgerEntry.entitlement_id == item.id,
                        LeaveBalanceLedgerEntry.organization_id == user.organization_id,
                    )
                )
            ).all()
        )

        def total(kinds: set[str]) -> Decimal:
            return sum((row.amount for row in rows if row.entry_type in kinds), Decimal("0"))

        accrued, carried, adjustments = (
            total({"accrual"}),
            total({"carryover"}),
            total({"adjustment"}),
        )
        used, expired = -total({"usage", "reversal"}), -total({"expiry"})
        pending = Decimal(
            str(
                await self.session.scalar(
                    select(func.coalesce(func.sum(LeaveRequest.duration_days), 0)).where(
                        LeaveRequest.organization_id == user.organization_id,
                        LeaveRequest.employee_id == item.employee_id,
                        LeaveRequest.leave_type_id == item.leave_type_id,
                        LeaveRequest.leave_period_id == item.leave_period_id,
                        LeaveRequest.status == "submitted",
                    )
                )
                or 0
            )
        )
        available = item.allocated_days + accrued + carried + adjustments - used - expired
        return BalanceResponse(
            entitlement_id=item.id,
            employee_id=item.employee_id,
            leave_type_id=item.leave_type_id,
            leave_period_id=item.leave_period_id,
            entitled=item.allocated_days,
            accrued=accrued,
            carried_forward=carried,
            adjustments=adjustments,
            used=used,
            pending=pending,
            expired=expired,
            available=available,
            available_after_pending=available - pending,
        )

    async def my_balances(self, user: User) -> list[BalanceResponse]:
        """Self-service balances limited to the authenticated employee's entitlements."""
        current_period_id = await self.session.scalar(
            select(LeavePeriod.id)
            .where(
                LeavePeriod.organization_id == user.organization_id,
                LeavePeriod.status == "open",
                LeavePeriod.start_date <= date.today(),
                LeavePeriod.end_date >= date.today(),
            )
            .order_by(LeavePeriod.start_date.desc())
            .limit(1)
        )
        if current_period_id is None:
            return []
        page = await self.list_balances(
            user,
            employee_id=user.id,
            leave_period_id=current_period_id,
            page=1,
            page_size=100,
            self_service=True,
        )
        return [BalanceResponse.model_validate(item) for item in page.items]

    async def list_balances(
        self,
        user: User,
        *,
        employee_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        leave_type_id: uuid.UUID | None = None,
        leave_period_id: uuid.UUID | None = None,
        search: str | None = None,
        sort_by: str = "employee",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 25,
        self_service: bool = False,
    ) -> BalancePage:
        if self_service and employee_id != user.id:
            raise AuthorizationError("Self-service balances must be scoped to the current user")
        if (
            not self_service
            and not self._manage(user)
            and not ({"leave.reports.view", "leave.export"} & self.permissions(user))
        ):
            raise AuthorizationError("You cannot view organization leave balances")
        zero = Decimal("0")
        ledger = (
            select(
                LeaveBalanceLedgerEntry.entitlement_id.label("eid"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                LeaveBalanceLedgerEntry.entry_type == "accrual",
                                LeaveBalanceLedgerEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("accrued"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                LeaveBalanceLedgerEntry.entry_type == "carryover",
                                LeaveBalanceLedgerEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("carried"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                LeaveBalanceLedgerEntry.entry_type == "adjustment",
                                LeaveBalanceLedgerEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("adjustments"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                LeaveBalanceLedgerEntry.entry_type.in_(("usage", "reversal")),
                                LeaveBalanceLedgerEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("usage_net"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                LeaveBalanceLedgerEntry.entry_type == "expiry",
                                LeaveBalanceLedgerEntry.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("expiry_net"),
            )
            .where(LeaveBalanceLedgerEntry.organization_id == user.organization_id)
            .group_by(LeaveBalanceLedgerEntry.entitlement_id)
            .subquery()
        )
        pending = (
            select(
                LeaveRequest.employee_id.label("employee_id"),
                LeaveRequest.leave_type_id.label("type_id"),
                LeaveRequest.leave_period_id.label("period_id"),
                func.sum(LeaveRequest.duration_days).label("pending"),
            )
            .where(
                LeaveRequest.organization_id == user.organization_id,
                LeaveRequest.status == "submitted",
            )
            .group_by(
                LeaveRequest.employee_id, LeaveRequest.leave_type_id, LeaveRequest.leave_period_id
            )
            .subquery()
        )
        query = (
            select(
                LeaveEntitlement,
                User,
                OrganizationUnit,
                LeaveType,
                LeavePeriod,
                ledger.c.accrued,
                ledger.c.carried,
                ledger.c.adjustments,
                ledger.c.usage_net,
                ledger.c.expiry_net,
                pending.c.pending,
            )
            .join(User, User.id == LeaveEntitlement.employee_id)
            .outerjoin(OrganizationUnit, OrganizationUnit.id == User.department_id)
            .join(LeaveType, LeaveType.id == LeaveEntitlement.leave_type_id)
            .join(LeavePeriod, LeavePeriod.id == LeaveEntitlement.leave_period_id)
            .outerjoin(ledger, ledger.c.eid == LeaveEntitlement.id)
            .outerjoin(
                pending,
                (pending.c.employee_id == LeaveEntitlement.employee_id)
                & (pending.c.type_id == LeaveEntitlement.leave_type_id)
                & (pending.c.period_id == LeaveEntitlement.leave_period_id),
            )
            .where(LeaveEntitlement.organization_id == user.organization_id)
        )
        if employee_id:
            query = query.where(LeaveEntitlement.employee_id == employee_id)
        if department_id:
            query = query.where(User.department_id == department_id)
        if leave_type_id:
            query = query.where(LeaveEntitlement.leave_type_id == leave_type_id)
        if leave_period_id:
            query = query.where(LeaveEntitlement.leave_period_id == leave_period_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    User.display_name.ilike(term),
                    User.employee_number.ilike(term),
                    LeaveType.name.ilike(term),
                )
            )
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        balance_sorts = {
            "employee": User.display_name,
            "department": OrganizationUnit.name,
            "leave_type": LeaveType.name,
            "period": LeavePeriod.start_date,
            "available": LeaveEntitlement.allocated_days
            + func.coalesce(ledger.c.accrued, 0)
            + func.coalesce(ledger.c.carried, 0)
            + func.coalesce(ledger.c.adjustments, 0)
            + func.coalesce(ledger.c.usage_net, 0)
            + func.coalesce(ledger.c.expiry_net, 0),
        }
        sort_column = balance_sorts.get(sort_by, User.display_name)
        ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        rows = (
            await self.session.execute(
                query.order_by(ordering, LeaveType.name, LeaveEntitlement.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        items: list[BalanceListItem] = []
        for (
            entitlement,
            employee,
            department,
            kind,
            period,
            accrued_value,
            carried_value,
            adjustment_value,
            usage_value,
            expiry_value,
            pending_value,
        ) in rows:
            accrued = Decimal(str(accrued_value or zero))
            carried = Decimal(str(carried_value or zero))
            adjustments = Decimal(str(adjustment_value or zero))
            used = -Decimal(str(usage_value or zero))
            expired = -Decimal(str(expiry_value or zero))
            pending_days = Decimal(str(pending_value or zero))
            available = (
                entitlement.allocated_days + accrued + carried + adjustments - used - expired
            )
            items.append(
                BalanceListItem(
                    entitlement_id=entitlement.id,
                    employee_id=employee.id,
                    leave_type_id=kind.id,
                    leave_period_id=period.id,
                    employee_number=employee.employee_number,
                    employee_name=employee.display_name,
                    department_id=employee.department_id,
                    department_name=department.name if department else None,
                    leave_type_name=kind.name,
                    leave_type_code=kind.code,
                    period_name=period.name,
                    entitled=entitlement.allocated_days,
                    accrued=accrued,
                    carried_forward=carried,
                    adjustments=adjustments,
                    used=used,
                    pending=pending_days,
                    expired=expired,
                    available=available,
                    available_after_pending=available - pending_days,
                )
            )
        return BalancePage(items=items, total=total, page=page, page_size=page_size)

    async def balance_history(
        self,
        user: User,
        *,
        employee_id: uuid.UUID | None,
        leave_type_id: uuid.UUID | None,
        leave_period_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> LedgerPage:
        target = employee_id or user.id
        if target != user.id and not self._manage(user):
            raise AuthorizationError("You cannot view this balance history")
        query = select(LeaveBalanceLedgerEntry).where(
            LeaveBalanceLedgerEntry.organization_id == user.organization_id,
            LeaveBalanceLedgerEntry.employee_id == target,
        )
        if leave_type_id:
            query = query.where(LeaveBalanceLedgerEntry.leave_type_id == leave_type_id)
        if leave_period_id:
            query = query.where(LeaveBalanceLedgerEntry.leave_period_id == leave_period_id)
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        LeaveBalanceLedgerEntry.effective_date.desc(),
                        LeaveBalanceLedgerEntry.id.desc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        actor_ids = {row.actor_id for row in rows if row.actor_id is not None}
        actor_names: dict[uuid.UUID, str] = {}
        if actor_ids:
            actors = list(
                (
                    await self.session.scalars(
                        select(User).where(
                            User.organization_id == user.organization_id,
                            User.id.in_(actor_ids),
                        )
                    )
                ).all()
            )
            actor_names = {
                actor.id: f"{actor.first_name} {actor.last_name}".strip() for actor in actors
            }
        return LedgerPage(
            items=[
                LedgerEntryResponse.model_validate(row).model_copy(
                    update={
                        "actor_name": (
                            actor_names.get(row.actor_id) if row.actor_id is not None else None
                        )
                    }
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_requests(
        self,
        user: User,
        *,
        scope: str,
        employee_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        leave_type_id: uuid.UUID | None = None,
        request_status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> LeaveRequestPage:
        query = select(LeaveRequest).where(
            LeaveRequest.organization_id == user.organization_id, LeaveRequest.deleted_at.is_(None)
        )
        if scope == "mine":
            query = query.where(LeaveRequest.employee_id == user.id)
        elif scope == "team":
            direct_reports = select(User.id).where(
                User.organization_id == user.organization_id, User.manager_id == user.id
            )
            query = query.where(LeaveRequest.employee_id.in_(direct_reports))
        elif scope in {"pending", "recently_reviewed"}:
            direct_reports = select(User.id).where(
                User.organization_id == user.organization_id, User.manager_id == user.id
            )
            query = query.where(LeaveRequest.employee_id.in_(direct_reports))
            if scope == "pending":
                query = query.where(LeaveRequest.status == "submitted")
            else:
                query = query.where(LeaveRequest.status.in_(("approved", "rejected")))
        elif scope == "organization" and not self._manage(user):
            raise AuthorizationError("You cannot view organization leave requests")
        if employee_id:
            query = query.where(LeaveRequest.employee_id == employee_id)
        if department_id:
            query = query.where(LeaveRequest.department_id == department_id)
        if leave_type_id:
            query = query.where(LeaveRequest.leave_type_id == leave_type_id)
        if request_status:
            query = query.where(LeaveRequest.status == request_status)
        if start_date:
            query = query.where(LeaveRequest.end_date >= start_date)
        if end_date:
            query = query.where(LeaveRequest.start_date <= end_date)
        if search:
            term = f"%{search.strip()}%"
            query = query.join(User, User.id == LeaveRequest.employee_id).join(
                LeaveType, LeaveType.id == LeaveRequest.leave_type_id
            )
            query = query.where(
                or_(
                    User.display_name.ilike(term),
                    User.employee_number.ilike(term),
                    LeaveType.name.ilike(term),
                )
            )
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        request_sorts = {
            "created_at": LeaveRequest.created_at,
            "start_date": LeaveRequest.start_date,
            "end_date": LeaveRequest.end_date,
            "status": LeaveRequest.status,
            "duration": LeaveRequest.duration_days,
        }
        sort_column = request_sorts.get(sort_by, LeaveRequest.created_at)
        ordering = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(ordering, LeaveRequest.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        reveal_reason = scope in {"mine", "team", "pending"} or self._manage(user)
        employee_ids = {row.employee_id for row in rows}
        department_ids = {row.department_id for row in rows if row.department_id}
        type_ids = {row.leave_type_id for row in rows}
        period_ids = {row.leave_period_id for row in rows}
        employees = {
            item.id: item
            for item in (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == user.organization_id,
                        User.id.in_(employee_ids),
                    )
                )
            ).all()
        }
        departments = {
            item.id: item
            for item in (
                await self.session.scalars(
                    select(OrganizationUnit).where(
                        OrganizationUnit.organization_id == user.organization_id,
                        OrganizationUnit.id.in_(department_ids),
                    )
                )
            ).all()
        }
        leave_types = {
            item.id: item
            for item in (
                await self.session.scalars(
                    select(LeaveType).where(
                        LeaveType.organization_id == user.organization_id,
                        LeaveType.id.in_(type_ids),
                    )
                )
            ).all()
        }
        periods = {
            item.id: item
            for item in (
                await self.session.scalars(
                    select(LeavePeriod).where(
                        LeavePeriod.organization_id == user.organization_id,
                        LeavePeriod.id.in_(period_ids),
                    )
                )
            ).all()
        }
        items: list[LeaveRequestResponse] = []
        for row in rows:
            employee = employees[row.employee_id]
            leave_type = leave_types[row.leave_type_id]
            period = periods[row.leave_period_id]
            department = departments.get(row.department_id) if row.department_id else None
            items.append(
                LeaveRequestResponse.model_validate(row).model_copy(
                    update={
                        "employee_number": employee.employee_number,
                        "employee_name": employee.display_name,
                        "department_name": department.name if department else None,
                        "leave_type_name": leave_type.name,
                        "leave_type_code": leave_type.code,
                        "leave_period_name": period.name,
                    }
                )
            )
        if not reveal_reason:
            items = [
                item.model_copy(update={"reason": None, "review_comment": None}) for item in items
            ]
        return LeaveRequestPage(items=items, total=total, page=page, page_size=page_size)

    async def request_detail(self, user: User, request_id: uuid.UUID) -> LeaveRequestDetail:
        request = await self._request(user, request_id)
        if not await self._can_view_request(user, request):
            raise NotFoundError("Leave request not found")
        employee = await self._employee(user, request.employee_id)
        manager = await self._employee(user, employee.manager_id) if employee.manager_id else None
        reviewer = (
            await self._employee(user, request.reviewed_by_id) if request.reviewed_by_id else None
        )
        department = (
            await self.session.scalar(
                select(OrganizationUnit).where(
                    OrganizationUnit.id == request.department_id,
                    OrganizationUnit.organization_id == user.organization_id,
                )
            )
            if request.department_id
            else None
        )
        leave_type = await self._type(user, request.leave_type_id)
        period = await self._period(user, period_id=request.leave_period_id)
        attachments = await self.list_attachments(user, request.id)
        history = list(
            (
                await self.session.scalars(
                    select(LeaveRequestHistory)
                    .where(
                        LeaveRequestHistory.organization_id == user.organization_id,
                        LeaveRequestHistory.leave_request_id == request.id,
                    )
                    .order_by(LeaveRequestHistory.created_at, LeaveRequestHistory.id)
                )
            ).all()
        )
        can_view_private = request.employee_id == user.id or await self._can_review(user, request)
        data = LeaveRequestResponse.model_validate(request).model_dump()
        if not can_view_private:
            data["reason"] = None
            data["review_comment"] = None
            attachments = []
            history = []
        data.update(
            {
                "employee_number": employee.employee_number,
                "employee_name": employee.display_name,
                "department_name": department.name if department else None,
                "manager_id": manager.id if manager else None,
                "manager_name": manager.display_name if manager else None,
                "leave_type_name": leave_type.name,
                "leave_type_code": leave_type.code,
                "leave_period_name": period.name,
                "reviewer_name": reviewer.display_name if reviewer else None,
                "balance_effect": (
                    -request.duration_days if request.status == "approved" else Decimal("0")
                ),
                "attachments": [
                    LeaveAttachmentResponse.model_validate(item) for item in attachments
                ],
                "history": [LeaveHistoryResponse.model_validate(item) for item in history],
            }
        )
        return LeaveRequestDetail.model_validate(data)

    async def my_summary(self, user: User) -> LeaveSummaryResponse:
        balances = await self.my_balances(user)
        pending = await self.list_requests(
            user, scope="mine", request_status="submitted", page_size=10
        )
        upcoming = await self.list_requests(
            user, scope="mine", request_status="approved", start_date=date.today(), page_size=10
        )
        recent = await self.list_requests(user, scope="mine", page_size=10)
        return LeaveSummaryResponse(
            balances=balances,
            pending_requests=pending.items,
            upcoming_approved=upcoming.items,
            recent_history=recent.items,
        )

    async def manager_summary(self, user: User) -> ManagerLeaveSummary:
        pending = await self.list_requests(user, scope="pending", page=1, page_size=10)
        recently_reviewed = await self.list_requests(
            user, scope="recently_reviewed", page=1, page_size=10
        )
        today = date.today()
        away = await self.team_availability(user, today, today)
        upcoming = await self.team_availability(
            user, today + timedelta(days=1), today + timedelta(days=30)
        )
        return ManagerLeaveSummary(
            pending_count=pending.total,
            pending=pending.items,
            away_today=away,
            upcoming=upcoming,
            recently_reviewed=recently_reviewed.items,
        )

    async def status_report(self, user: User, category: str) -> list[LeaveStatusSummary]:
        if not ({"leave.reports.view", "leave.export"} & self.permissions(user)):
            raise AuthorizationError("You cannot view leave reports")
        today = date.today()
        query = select(
            LeaveRequest.status,
            func.count(LeaveRequest.id),
            func.coalesce(func.sum(LeaveRequest.duration_days), 0),
        ).where(
            LeaveRequest.organization_id == user.organization_id,
            LeaveRequest.deleted_at.is_(None),
        )
        if category == "pending":
            query = query.where(LeaveRequest.status == "submitted")
        elif category == "current":
            query = query.where(
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
        elif category == "upcoming":
            query = query.where(LeaveRequest.status == "approved", LeaveRequest.start_date > today)
        query = query.group_by(LeaveRequest.status).order_by(LeaveRequest.status)
        rows = (await self.session.execute(query)).all()
        return [
            LeaveStatusSummary(
                status=status, request_count=int(count), total_days=Decimal(str(days))
            )
            for status, count, days in rows
        ]

    async def team_availability(
        self, user: User, start_date: date, end_date: date
    ) -> list[LeaveAvailabilityItem]:
        if "leave.view_team" not in self.permissions(user) and not self._manage(user):
            raise AuthorizationError("You cannot view team leave availability")
        query = (
            select(LeaveRequest, User)
            .join(User, User.id == LeaveRequest.employee_id)
            .where(
                LeaveRequest.organization_id == user.organization_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
                LeaveRequest.deleted_at.is_(None),
            )
        )
        if not self._manage(user):
            query = query.where(User.manager_id == user.id)
        rows = (await self.session.execute(query.order_by(LeaveRequest.start_date))).all()
        return [
            LeaveAvailabilityItem(
                employee_id=employee.id,
                employee_name=employee.display_name,
                start_date=request.start_date,
                end_date=request.end_date,
            )
            for request, employee in rows
        ]

    async def usage_report(self, user: User, group_by: str) -> list[LeaveReportRow]:
        if not (
            {"leave.reports.view", "leave.export"} & self.permissions(user)
        ) and not self._manage(user):
            raise AuthorizationError("You cannot view leave reports")
        if group_by == "department":
            query = (
                select(
                    OrganizationUnit.id,
                    OrganizationUnit.name,
                    func.count(LeaveRequest.id),
                    func.coalesce(func.sum(LeaveRequest.duration_days), 0),
                )
                .join(LeaveRequest, LeaveRequest.department_id == OrganizationUnit.id)
                .where(
                    LeaveRequest.organization_id == user.organization_id,
                    LeaveRequest.status == "approved",
                )
                .group_by(OrganizationUnit.id, OrganizationUnit.name)
            )
        else:
            query = (
                select(
                    LeaveType.id,
                    LeaveType.name,
                    func.count(LeaveRequest.id),
                    func.coalesce(func.sum(LeaveRequest.duration_days), 0),
                )
                .join(LeaveRequest, LeaveRequest.leave_type_id == LeaveType.id)
                .where(
                    LeaveRequest.organization_id == user.organization_id,
                    LeaveRequest.status == "approved",
                )
                .group_by(LeaveType.id, LeaveType.name)
            )
        rows = (await self.session.execute(query)).all()
        return [
            LeaveReportRow(
                key=str(key), label=label, request_count=int(count), total_days=Decimal(str(days))
            )
            for key, label, count, days in rows
        ]

    async def adjust(
        self, user: User, entitlement_id: uuid.UUID, body: AdjustmentInput
    ) -> AdjustmentResponse:
        item = await self.session.scalar(
            select(LeaveEntitlement)
            .where(
                LeaveEntitlement.id == entitlement_id,
                LeaveEntitlement.organization_id == user.organization_id,
            )
            .with_for_update()
        )
        if item is None:
            raise NotFoundError("Leave entitlement not found")
        previous = await self.balance(user, item.id)
        amount = -body.amount if body.operation == "deduct" else body.amount
        entry = await self._ledger(
            user, item, "adjustment", amount, body.effective_date, body.reason
        )
        if entry is None:  # adjustments do not use idempotency keys
            raise RuntimeError("Leave adjustment was not persisted")
        self._audit(
            user,
            "leave.balance.adjusted",
            item.id,
            {"operation": body.operation, "amount": str(amount), "reason": body.reason},
        )
        await self.session.flush()
        resulting = await self.balance(user, item.id)
        return AdjustmentResponse(
            previous_balance=previous,
            adjustment=LedgerEntryResponse.model_validate(entry),
            resulting_balance=resulting,
        )

    async def adjust_by_dimensions(
        self, user: User, body: ControlledAdjustmentInput
    ) -> AdjustmentResponse:
        await self._employee(user, body.employee_id)
        entitlement_id = await self.session.scalar(
            select(LeaveEntitlement.id).where(
                LeaveEntitlement.organization_id == user.organization_id,
                LeaveEntitlement.employee_id == body.employee_id,
                LeaveEntitlement.leave_type_id == body.leave_type_id,
                LeaveEntitlement.leave_period_id == body.leave_period_id,
            )
        )
        if entitlement_id is None:
            raise NotFoundError("Leave entitlement not found")
        return await self.adjust(
            user,
            entitlement_id,
            AdjustmentInput(
                operation=body.operation,
                amount=body.amount,
                effective_date=body.effective_date,
                reason=body.reason,
            ),
        )

    async def working_week(self, user: User) -> WorkingWeekResponse:
        organization = await self.session.get(Organization, user.organization_id)
        settings = organization.settings if organization else {}
        weekdays = settings.get("leave_working_weekdays", [0, 1, 2, 3, 4])
        exclude = settings.get("leave_exclude_holidays", True)
        safe_weekdays = (
            [int(day) for day in weekdays if isinstance(day, int) and 0 <= day <= 6]
            if isinstance(weekdays, list)
            else [0, 1, 2, 3, 4]
        )
        return WorkingWeekResponse(
            weekdays=safe_weekdays or [0, 1, 2, 3, 4], exclude_holidays=bool(exclude)
        )

    async def update_working_week(self, user: User, body: WorkingWeekInput) -> WorkingWeekResponse:
        organization = await self.session.get(Organization, user.organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        organization.settings = {
            **(organization.settings or {}),
            "leave_working_weekdays": sorted(body.weekdays),
            "leave_exclude_holidays": body.exclude_holidays,
        }
        self._audit(user, "leave.working_week.updated", organization.id)
        await self.session.flush()
        return WorkingWeekResponse(
            weekdays=sorted(body.weekdays), exclude_holidays=body.exclude_holidays
        )

    async def working_days(
        self, user: User, start: date, end: date, half_day: bool = False
    ) -> WorkingDayResult:
        policy = await self.working_week(user)
        holidays = set(
            (
                await self.session.scalars(
                    select(Holiday.date).where(
                        Holiday.organization_id == user.organization_id,
                        Holiday.date >= start,
                        Holiday.date <= end,
                    )
                )
            ).all()
        )
        if not policy.exclude_holidays:
            holidays.clear()
        current = start
        weekends = holidays_count = 0
        chargeable = Decimal("0")
        while current <= end:
            if current.weekday() not in policy.weekdays:
                weekends += 1
            elif current in holidays:
                holidays_count += 1
            else:
                chargeable += 1
            current += timedelta(days=1)
        if half_day and chargeable:
            chargeable = Decimal("0.5")
        return WorkingDayResult(
            calendar_span=(end - start).days + 1,
            excluded_non_working_days=weekends,
            excluded_holidays=holidays_count,
            chargeable_days=chargeable,
        )

    async def _request(self, user: User, request_id: uuid.UUID, lock: bool = False) -> LeaveRequest:
        statement = select(LeaveRequest).where(
            LeaveRequest.id == request_id,
            LeaveRequest.organization_id == user.organization_id,
            LeaveRequest.deleted_at.is_(None),
        )
        if lock:
            statement = statement.with_for_update()
        item = await self.session.scalar(statement)
        if item is None:
            raise NotFoundError("Leave request not found")
        return item

    async def _history(
        self, user: User, request: LeaveRequest, event: str, comment: str | None = None
    ) -> None:
        self.session.add(
            LeaveRequestHistory(
                organization_id=user.organization_id,
                leave_request_id=request.id,
                actor_id=user.id,
                event_type=event,
                comment=comment,
            )
        )

    async def _can_view_request(self, actor: User, request: LeaveRequest) -> bool:
        if request.employee_id == actor.id or self._manage(actor):
            return True
        employee = await self._employee(actor, request.employee_id)
        return employee.manager_id == actor.id and bool(
            {"leave.view_team", "leave.review", "leave.approve", "leave.reject"}
            & self.permissions(actor)
        )

    async def ensure_attachment_access(self, actor: User, request_id: uuid.UUID) -> LeaveRequest:
        request = await self._request(actor, request_id)
        if not await self._can_view_request(actor, request):
            raise AuthorizationError("You are not authorized to access this leave document")
        return request

    async def add_attachment(
        self,
        actor: User,
        request_id: uuid.UUID,
        *,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
    ) -> LeaveAttachment:
        request = await self.ensure_attachment_access(actor, request_id)
        if request.status in {"cancelled", "rejected", "withdrawn"}:
            raise ValidationError("Documents cannot be added to a closed leave request")
        item = LeaveAttachment(
            organization_id=actor.organization_id,
            leave_request_id=request.id,
            filename=filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255],
            content_type=content_type,
            size=size,
            storage_key=storage_key,
            uploaded_by_id=actor.id,
        )
        self.session.add(item)
        await self.session.flush()
        self._audit(actor, "leave.attachment.added", request.id, {"attachment_id": str(item.id)})
        return item

    async def list_attachments(self, actor: User, request_id: uuid.UUID) -> list[LeaveAttachment]:
        await self.ensure_attachment_access(actor, request_id)
        return list(
            (
                await self.session.scalars(
                    select(LeaveAttachment)
                    .where(
                        LeaveAttachment.organization_id == actor.organization_id,
                        LeaveAttachment.leave_request_id == request_id,
                        LeaveAttachment.deleted_at.is_(None),
                    )
                    .order_by(LeaveAttachment.created_at, LeaveAttachment.id)
                )
            ).all()
        )

    async def attachment_for_download(
        self, actor: User, request_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> LeaveAttachment:
        await self.ensure_attachment_access(actor, request_id)
        item = await self.session.scalar(
            select(LeaveAttachment).where(
                LeaveAttachment.id == attachment_id,
                LeaveAttachment.leave_request_id == request_id,
                LeaveAttachment.organization_id == actor.organization_id,
                LeaveAttachment.deleted_at.is_(None),
            )
        )
        if item is None:
            raise NotFoundError("Leave attachment not found")
        return item

    async def delete_attachment(
        self, actor: User, request_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> str:
        request = await self.ensure_attachment_access(actor, request_id)
        item = await self.attachment_for_download(actor, request_id, attachment_id)
        if item.uploaded_by_id != actor.id and not self._manage(actor):
            raise AuthorizationError("You are not authorized to remove this leave document")
        item.soft_delete(actor.id)
        self._audit(actor, "leave.attachment.removed", request.id, {"attachment_id": str(item.id)})
        return item.storage_key

    async def has_attachments(self, organization_id: uuid.UUID, request_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(LeaveAttachment.id).where(
                    LeaveAttachment.organization_id == organization_id,
                    LeaveAttachment.leave_request_id == request_id,
                    LeaveAttachment.deleted_at.is_(None),
                )
            )
        )

    async def _notify_best_effort(
        self,
        recipient_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        request: LeaveRequest,
    ) -> None:
        """Notification routing must never roll back an otherwise valid leave transition."""
        try:
            await NotificationService(self.session, get_settings()).create_notification(
                organization_id=request.organization_id,
                user_id=recipient_id,
                notification_type=notification_type,
                category="leave",
                priority="normal",
                title=title,
                body=body,
                action_url=f"/leave/requests/{request.id}",
                metadata={"leave_request_id": str(request.id)},
            )
        except Exception:  # routing/push delivery must not corrupt the leave workflow
            await logger.aexception("leave_notification_failed", leave_request_id=str(request.id))
        try:
            recipient = await self.session.scalar(
                select(User).where(
                    User.id == recipient_id,
                    User.organization_id == request.organization_id,
                    User.removed_at.is_(None),
                )
            )
            if recipient is None:
                raise NotFoundError("Notification recipient not found")
            employee = await self.session.scalar(
                select(User).where(
                    User.id == request.employee_id,
                    User.organization_id == request.organization_id,
                )
            )
            if employee is None:
                raise NotFoundError("Leave employee not found")
            leave_type = await self.session.get(LeaveType, request.leave_type_id)
            sender = await MeetingEmailSender.for_organization(
                self.session, get_settings(), request.organization_id
            )
            template_key = cast(TemplateKey, notification_type)
            rendered = EmailTemplateRegistry.render(
                template_key,
                LeaveEmailData(
                    leave_url=f"{get_settings().web_app_url.rstrip('/')}/leave/requests/{request.id}",
                    employee_name=employee.display_name,
                    leave_type=leave_type.name if leave_type else "Leave",
                    date_range=(
                        f"{request.start_date.isoformat()} to {request.end_date.isoformat()}"
                    ),
                    working_days=str(request.duration_days),
                    note=body,
                ),
                sender.branding,
            )
            transport_id = await sender.send_rendered(
                recipient.email,
                rendered,
                message_key=f"leave-{request.id}-{notification_type}-{recipient.id}",
            )
            self.session.add(
                AuditLog(
                    organization_id=request.organization_id,
                    user_id=None,
                    action=(
                        "leave.delivery.accepted"
                        if sender.delivery_mode == "smtp"
                        else "leave.delivery.local_outbox"
                    ),
                    resource="leave",
                    resource_id=request.id,
                    audit_metadata={
                        "event_type": notification_type,
                        "recipient_domain": recipient.email.rpartition("@")[2].lower(),
                        "transport_id": transport_id if sender.delivery_mode == "smtp" else None,
                        "template_key": rendered.key,
                        "template_version": rendered.version,
                    },
                )
            )
        except Exception as error:
            self.session.add(
                AuditLog(
                    organization_id=request.organization_id,
                    user_id=None,
                    action="leave.delivery.failed",
                    resource="leave",
                    resource_id=request.id,
                    audit_metadata={
                        "event_type": notification_type,
                        "error_type": type(error).__name__,
                    },
                )
            )

    async def _upsert_calendar_event(self, actor: User, request: LeaveRequest) -> None:
        employee = await self._employee(actor, request.employee_id)
        calendar = await self.session.scalar(
            select(Calendar).where(
                Calendar.organization_id == actor.organization_id,
                Calendar.owner_id == request.employee_id,
                Calendar.type == CalendarType.PERSONAL,
                Calendar.deleted_at.is_(None),
            )
        )
        if calendar is None:
            calendar = Calendar(
                organization_id=request.organization_id,
                workspace_id=employee.workspace_id,
                owner_id=request.employee_id,
                name="My Calendar",
                type=CalendarType.PERSONAL,
                timezone=employee.timezone,
                visibility=Visibility.PRIVATE,
                is_default=True,
            )
            self.session.add(calendar)
            await self.session.flush()
        start = datetime.combine(request.start_date, datetime.min.time(), UTC)
        end = datetime.combine(request.end_date + timedelta(days=1), datetime.min.time(), UTC)
        event = None
        if request.calendar_event_id:
            event = await self.session.scalar(
                select(CalendarEvent).where(
                    CalendarEvent.id == request.calendar_event_id,
                    CalendarEvent.calendar_id == calendar.id,
                )
            )
        if event is None:
            event = CalendarEvent(
                calendar_id=calendar.id,
                title="Away",
                description=None,
                start_datetime=start,
                end_datetime=end,
                timezone="UTC",
                status=EventStatus.CONFIRMED,
                visibility=Visibility.MEMBERS,
                all_day=True,
                created_by=actor.id,
                updated_by=actor.id,
            )
            self.session.add(event)
            await self.session.flush()
            request.calendar_event_id = event.id
        else:
            event.title, event.description = "Away", None
            event.start_datetime, event.end_datetime = start, end
            event.status, event.updated_by = EventStatus.CONFIRMED, actor.id

    async def _remove_calendar_event(self, actor: User, request: LeaveRequest) -> None:
        if request.calendar_event_id is None:
            return
        event = await self.session.scalar(
            select(CalendarEvent).where(CalendarEvent.id == request.calendar_event_id)
        )
        if event is not None and event.deleted_at is None:
            event.soft_delete(actor.id)

    async def create_request(self, user: User, body: LeaveRequestInput) -> LeaveRequest:
        employee = await self._employee(user, user.id)
        if employee.status != UserStatus.ACTIVE or employee.employment_status in {
            "terminated",
            "inactive",
        }:
            raise ValidationError("Inactive employees cannot request leave")
        kind = await self._type(user, body.leave_type_id, True)
        period = await self._period(user, on_date=body.start_date)
        if body.half_day and not kind.half_day_supported:
            raise ValidationError("This leave type does not support half-day requests")
        if body.end_date > period.end_date:
            raise ValidationError("Leave must be within the active leave period")
        if (
            kind.eligible_employment_types
            and employee.employment_type not in kind.eligible_employment_types.split(",")
        ):
            raise ValidationError("This leave type is not available for your employment type")
        if employee.employment_status == "probation" and not kind.probation_eligible:
            raise ValidationError("This leave type is not available during probation")
        if (body.start_date - date.today()).days < kind.minimum_notice_days:
            raise ValidationError(
                f"This leave type requires {kind.minimum_notice_days} days' notice"
            )
        result = await self.working_days(user, body.start_date, body.end_date, body.half_day)
        if not result.chargeable_days:
            raise ValidationError("The selected dates contain no working days")
        if (
            kind.maximum_consecutive_days is not None
            and result.chargeable_days > kind.maximum_consecutive_days
        ):
            raise ValidationError(
                f"This leave type permits at most {kind.maximum_consecutive_days} consecutive days"
            )
        item = LeaveRequest(
            organization_id=user.organization_id,
            employee_id=user.id,
            department_id=employee.department_id,
            leave_type_id=kind.id,
            leave_period_id=period.id,
            start_date=body.start_date,
            end_date=body.end_date,
            duration_days=result.chargeable_days,
            half_day=body.half_day,
            reason=body.reason,
        )
        self.session.add(item)
        await self.session.flush()
        await self._history(user, item, "draft_created")
        self._audit(user, "leave.request.drafted", item.id)
        return item

    async def submit(self, user: User, request_id: uuid.UUID) -> LeaveRequest:
        item = await self._request(user, request_id, True)
        if item.employee_id != user.id:
            raise AuthorizationError("You can only submit your own leave request")
        if item.status != "draft":
            raise ValidationError("Only draft leave requests can be submitted")
        leave_type = await self._type(user, item.leave_type_id, active=True)
        if leave_type.attachment_required and not await self.has_attachments(
            user.organization_id, item.id
        ):
            raise ValidationError(
                "Supporting documentation is required before submitting this leave request"
            )
        overlap = await self.session.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.organization_id == user.organization_id,
                LeaveRequest.employee_id == user.id,
                LeaveRequest.id != item.id,
                LeaveRequest.status.in_(("submitted", "approved")),
                LeaveRequest.start_date <= item.end_date,
                LeaveRequest.end_date >= item.start_date,
            )
        )
        if overlap:
            raise ValidationError("This leave request overlaps an existing request")
        entitlement = await self.session.scalar(
            select(LeaveEntitlement).where(
                LeaveEntitlement.organization_id == user.organization_id,
                LeaveEntitlement.employee_id == user.id,
                LeaveEntitlement.leave_type_id == item.leave_type_id,
                LeaveEntitlement.leave_period_id == item.leave_period_id,
            )
        )
        if entitlement is None:
            raise ValidationError("No leave entitlement is available for this request")
        if (await self.balance(user, entitlement.id)).available_after_pending < item.duration_days:
            raise ValidationError("Insufficient leave balance")
        item.status = "submitted"
        await self._history(user, item, "submitted")
        self._audit(user, "leave.request.submitted", item.id)
        employee = await self._employee(user, item.employee_id)
        if employee.manager_id:
            await self._notify_best_effort(
                employee.manager_id,
                "leave.submitted",
                "Leave request awaiting review",
                "A direct report submitted a leave request.",
                item,
            )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def review(
        self, user: User, request_id: uuid.UUID, action: str, comment: str | None = None
    ) -> LeaveRequest:
        item = await self._request(user, request_id, True)
        if not await self._can_review(user, item):
            raise AuthorizationError("You are not authorized to review this request")
        if item.status != "submitted":
            raise ValidationError("Only submitted leave requests can be reviewed")
        if action == "rejected" and not comment:
            raise ValidationError("A rejection reason is required")
        if action == "approved":
            entitlement = await self.session.scalar(
                select(LeaveEntitlement)
                .where(
                    LeaveEntitlement.organization_id == user.organization_id,
                    LeaveEntitlement.employee_id == item.employee_id,
                    LeaveEntitlement.leave_type_id == item.leave_type_id,
                    LeaveEntitlement.leave_period_id == item.leave_period_id,
                )
                .with_for_update()
            )
            if (
                entitlement is None
                or (await self.balance(user, entitlement.id)).available < item.duration_days
            ):
                raise ValidationError("Insufficient leave balance")
            await self._ledger(
                user,
                entitlement,
                "usage",
                -item.duration_days,
                item.start_date,
                "Approved leave request",
                item.id,
            )
        item.status = action
        item.reviewed_by_id = user.id
        item.reviewed_at = datetime.now(UTC)
        item.review_comment = comment
        await self._history(user, item, action, comment)
        self._audit(user, f"leave.request.{action}", item.id)
        if action == "approved":
            await self._upsert_calendar_event(user, item)
        await self._notify_best_effort(
            item.employee_id,
            f"leave.{action}",
            f"Leave request {action}",
            comment or f"Your leave request was {action}.",
            item,
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def withdraw(self, user: User, request_id: uuid.UUID) -> LeaveRequest:
        item = await self._request(user, request_id, True)
        if item.employee_id != user.id:
            raise AuthorizationError("You can only withdraw your own leave request")
        if item.status != "submitted":
            raise ValidationError("Only submitted leave requests can be withdrawn")
        item.status = "withdrawn"
        await self._history(user, item, "withdrawn")
        self._audit(user, "leave.request.withdrawn", item.id)
        employee = await self._employee(user, item.employee_id)
        if employee.manager_id:
            await self._notify_best_effort(
                employee.manager_id,
                "leave.withdrawn",
                "Leave request withdrawn",
                "A direct report withdrew a leave request.",
                item,
            )
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def cancel(
        self, user: User, request_id: uuid.UUID, comment: str | None = None
    ) -> LeaveRequest:
        item = await self._request(user, request_id, True)
        if item.status != "approved":
            raise ValidationError("Only approved leave requests can be cancelled")
        if item.employee_id != user.id and not self._manage(user):
            raise AuthorizationError("You are not authorized to cancel this leave request")
        entitlement = await self.session.scalar(
            select(LeaveEntitlement)
            .where(
                LeaveEntitlement.organization_id == user.organization_id,
                LeaveEntitlement.employee_id == item.employee_id,
                LeaveEntitlement.leave_type_id == item.leave_type_id,
                LeaveEntitlement.leave_period_id == item.leave_period_id,
            )
            .with_for_update()
        )
        if entitlement is None:
            raise ValidationError("Leave entitlement is unavailable")
        await self._ledger(
            user,
            entitlement,
            "reversal",
            item.duration_days,
            date.today(),
            comment or "Approved leave cancelled",
            item.id,
        )
        item.status = "cancelled"
        await self._history(user, item, "cancelled", comment)
        await self._remove_calendar_event(user, item)
        self._audit(user, "leave.request.cancelled", item.id)
        await self._notify_best_effort(
            item.employee_id,
            "leave.cancelled",
            "Leave request cancelled",
            comment or "Your approved leave request was cancelled.",
            item,
        )
        await self.session.flush()
        await self.session.refresh(item)
        return item
