"""Tenant-isolated Leave Management application service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
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
    BalanceResponse,
    EntitlementInput,
    LeavePeriodInput,
    LeaveRequestInput,
    LeaveTypeInput,
    WorkingDayResult,
)
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.shared.exceptions import AuthorizationError, NotFoundError, ValidationError


class LeaveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def permissions(user: User) -> set[str]:
        return {p.name for role in user.roles for p in role.permissions}

    def _manage(self, user: User) -> bool:
        return bool({"leave.types.manage", "leave.balances.adjust"} & self.permissions(user))

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

    async def list_types(self, user: User) -> list[LeaveType]:
        return list(
            (
                await self.session.scalars(
                    select(LeaveType)
                    .where(
                        LeaveType.organization_id == user.organization_id,
                        LeaveType.deleted_at.is_(None),
                    )
                    .order_by(LeaveType.name)
                )
            ).all()
        )

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
            **body.model_dump(exclude={"eligible_employment_types"}),
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
    ) -> None:
        self.session.add(
            LeaveBalanceLedgerEntry(
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
                actor_id=actor.id,
            )
        )

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

    async def adjust(
        self, user: User, entitlement_id: uuid.UUID, body: AdjustmentInput
    ) -> BalanceResponse:
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
        await self._ledger(user, item, "adjustment", body.amount, body.effective_date, body.reason)
        self._audit(user, "leave.balance.adjusted", item.id)
        await self.session.flush()
        return await self.balance(user, item.id)

    async def working_days(
        self, user: User, start: date, end: date, half_day: bool = False
    ) -> WorkingDayResult:
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
        current = start
        weekends = holidays_count = 0
        chargeable = Decimal("0")
        while current <= end:
            if current.weekday() >= 5:
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
            return

    async def _upsert_calendar_event(self, actor: User, request: LeaveRequest) -> None:
        calendar = await self.session.scalar(
            select(Calendar).where(
                Calendar.organization_id == actor.organization_id,
                Calendar.owner_id == request.employee_id,
                Calendar.type == CalendarType.PERSONAL,
                Calendar.deleted_at.is_(None),
            )
        )
        if calendar is None:
            return
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
        result = await self.working_days(user, body.start_date, body.end_date, body.half_day)
        if not result.chargeable_days:
            raise ValidationError("The selected dates contain no working days")
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
        return item
