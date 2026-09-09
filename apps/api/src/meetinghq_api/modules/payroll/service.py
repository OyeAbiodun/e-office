"""Payroll orchestration over canonical employees, Leave, Finance, and notifications."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.finance.models import FinanceAccount, FinanceTransaction
from meetinghq_api.modules.leave.models import LeaveRequest, LeaveType
from meetinghq_api.modules.notifications.email_templates import (
    EmailTemplateRegistry,
    PayrollEmailData,
)
from meetinghq_api.modules.notifications.service import MeetingEmailSender, NotificationService
from meetinghq_api.modules.organizations.models import OrganizationUnit
from meetinghq_api.modules.payroll.calculations import (
    ZERO,
    CalculationInput,
    calculate,
    money,
    proration_factor,
)
from meetinghq_api.modules.payroll.models import (
    EmployeeSalaryStructure,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollHistory,
    PayrollLoan,
    PayrollLoanRepayment,
    PayrollPayment,
    PayrollPeriod,
    PayrollResultItem,
    PayrollRun,
    SalaryComponent,
    SalaryStructureItem,
    StatutoryConfiguration,
)
from meetinghq_api.modules.payroll.schemas import (
    PayrollAdjustmentInput,
    PayrollLoanInput,
    PayrollPaymentInput,
    PayrollPeriodInput,
    PayrollReversalInput,
    SalaryComponentInput,
    SalaryStructureInput,
    StatutoryConfigurationInput,
)
from meetinghq_api.modules.users.models import Permission, Role, User, UserStatus
from meetinghq_api.shared.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

EDITABLE_RUN = {"draft", "returned", "prepared"}


class PayrollService:
    """All Payroll writes are performed in the request transaction."""

    def __init__(self, session: AsyncSession, notifications: NotificationService) -> None:
        self.session = session
        self.notifications = notifications
        self.events = TransactionalDomainEventPublisher(session)

    @staticmethod
    def permissions(actor: User) -> set[str]:
        return {permission.name for role in actor.roles for permission in role.permissions}

    @classmethod
    def has(cls, actor: User, permission: str) -> bool:
        return permission in cls.permissions(actor)

    @classmethod
    def require(cls, actor: User, permission: str) -> None:
        if not cls.has(actor, permission):
            raise AuthorizationError(f"Permission required: {permission}")

    async def employee(self, actor: User, employee_id: uuid.UUID) -> User:
        employee = await self.session.scalar(
            select(User).where(
                User.id == employee_id,
                User.organization_id == actor.organization_id,
                User.removed_at.is_(None),
            )
        )
        if employee is None:
            raise NotFoundError("Employee not found")
        return employee

    async def period(
        self, actor: User, period_id: uuid.UUID, *, lock: bool = False
    ) -> PayrollPeriod:
        statement = select(PayrollPeriod).where(
            PayrollPeriod.id == period_id,
            PayrollPeriod.organization_id == actor.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        period = await self.session.scalar(statement)
        if period is None:
            raise NotFoundError("Payroll period not found")
        return period

    async def run(self, actor: User, run_id: uuid.UUID, *, lock: bool = False) -> PayrollRun:
        statement = select(PayrollRun).where(
            PayrollRun.id == run_id,
            PayrollRun.organization_id == actor.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        run = await self.session.scalar(statement)
        if run is None:
            raise NotFoundError("Payroll run not found")
        return run

    def audit(
        self,
        actor: User,
        action: str,
        resource: str,
        resource_id: uuid.UUID,
        **metadata: object,
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                audit_metadata=metadata,
            )
        )

    async def history(
        self,
        actor: User,
        run: PayrollRun,
        event_type: str,
        reason: str | None = None,
        **payload: object,
    ) -> None:
        self.session.add(
            PayrollHistory(
                organization_id=actor.organization_id,
                payroll_run_id=run.id,
                actor_id=actor.id,
                event_type=event_type,
                reason=reason,
                payload=payload,
            )
        )
        self.audit(actor, f"payroll.{event_type}", "payroll_run", run.id, **payload)

    async def notify_permission(
        self,
        actor: User,
        permission: str,
        notification_type: str,
        title: str,
        body: str,
        run: PayrollRun,
    ) -> None:
        recipients = list(
            (
                await self.session.scalars(
                    select(User)
                    .where(
                        User.organization_id == actor.organization_id,
                        User.status == UserStatus.ACTIVE,
                        User.removed_at.is_(None),
                        User.id != actor.id,
                        User.roles.any(Role.permissions.any(Permission.name == permission)),
                    )
                    .options(selectinload(User.roles).selectinload(Role.permissions))
                )
            ).all()
        )
        for recipient in recipients:
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=recipient.id,
                notification_type=notification_type,
                title=title,
                body=body,
                category="payroll",
                priority="high",
                metadata={"payroll_run_id": str(run.id)},
                action_url=f"/payroll/runs/{run.id}",
            )

    async def create_component(self, actor: User, body: SalaryComponentInput) -> SalaryComponent:
        self.require(actor, "payroll.components.manage")
        duplicate = await self.session.scalar(
            select(SalaryComponent.id).where(
                SalaryComponent.organization_id == actor.organization_id,
                func.lower(SalaryComponent.code) == body.code.lower(),
            )
        )
        if duplicate:
            raise ConflictError("A salary component with this code already exists")
        item = SalaryComponent(
            organization_id=actor.organization_id,
            created_by_id=actor.id,
            code=body.code.upper(),
            **body.model_dump(exclude={"code"}),
        )
        self.session.add(item)
        await self.session.flush()
        self.audit(actor, "payroll.component.created", "salary_component", item.id, code=item.code)
        return item

    async def update_component(
        self, actor: User, component_id: uuid.UUID, body: SalaryComponentInput
    ) -> SalaryComponent:
        self.require(actor, "payroll.components.manage")
        item = await self.session.scalar(
            select(SalaryComponent).where(
                SalaryComponent.id == component_id,
                SalaryComponent.organization_id == actor.organization_id,
                SalaryComponent.deleted_at.is_(None),
            )
        )
        if item is None:
            raise NotFoundError("Salary component not found")
        if item.is_system and body.code.upper() != item.code:
            raise ValidationError("System component codes cannot be changed")
        duplicate = await self.session.scalar(
            select(SalaryComponent.id).where(
                SalaryComponent.organization_id == actor.organization_id,
                func.lower(SalaryComponent.code) == body.code.lower(),
                SalaryComponent.id != item.id,
            )
        )
        if duplicate:
            raise ConflictError("A salary component with this code already exists")
        for key, value in body.model_dump().items():
            setattr(item, key, value)
        item.code = item.code.upper()
        self.audit(actor, "payroll.component.changed", "salary_component", item.id, code=item.code)
        return item

    async def list_components(
        self, actor: User, *, active: bool | None = None
    ) -> list[SalaryComponent]:
        self.require(actor, "payroll.salary_structure.view")
        query = select(SalaryComponent).where(
            SalaryComponent.organization_id == actor.organization_id,
            SalaryComponent.deleted_at.is_(None),
        )
        if active is not None:
            query = query.where(SalaryComponent.is_active == active)
        return list((await self.session.scalars(query.order_by(SalaryComponent.name))).all())

    async def create_statutory(
        self, actor: User, body: StatutoryConfigurationInput
    ) -> StatutoryConfiguration:
        self.require(actor, "payroll.statutory.manage")
        overlap = await self.session.scalar(
            select(StatutoryConfiguration.id).where(
                StatutoryConfiguration.organization_id == actor.organization_id,
                StatutoryConfiguration.configuration_type == body.configuration_type,
                StatutoryConfiguration.is_active.is_(True),
                StatutoryConfiguration.effective_start <= (body.effective_end or date.max),
                or_(
                    StatutoryConfiguration.effective_end.is_(None),
                    StatutoryConfiguration.effective_end >= body.effective_start,
                ),
            )
        )
        if overlap:
            raise ConflictError("An effective statutory configuration already covers these dates")
        self._validate_statutory_rules(body)
        item = StatutoryConfiguration(
            organization_id=actor.organization_id,
            created_by_id=actor.id,
            **body.model_dump(),
        )
        self.session.add(item)
        await self.session.flush()
        self.audit(
            actor,
            "payroll.statutory.created",
            "statutory_configuration",
            item.id,
            configuration_type=item.configuration_type,
            effective_start=item.effective_start.isoformat(),
        )
        return item

    @staticmethod
    def _validate_statutory_rules(body: StatutoryConfigurationInput) -> None:
        rules = body.rules
        if body.configuration_type == "paye" and not isinstance(rules.get("bands"), list):
            raise ValidationError("PAYE rules require configured bands")
        if body.configuration_type == "pension":
            for key in ("employee_rate", "employer_rate"):
                if key not in rules:
                    raise ValidationError(f"Pension rules require {key}")
        if body.configuration_type == "nhf" and "employee_rate" not in rules:
            raise ValidationError("NHF rules require employee_rate")
        if body.configuration_type == "payroll_policy":
            method = rules.get("proration_method", "calendar_days")
            if method not in {"calendar_days", "working_days"}:
                raise ValidationError("Invalid payroll proration policy")

    async def list_statutory(
        self, actor: User, configuration_type: str | None = None
    ) -> list[StatutoryConfiguration]:
        self.require(actor, "payroll.salary_structure.view")
        query = select(StatutoryConfiguration).where(
            StatutoryConfiguration.organization_id == actor.organization_id
        )
        if configuration_type:
            query = query.where(StatutoryConfiguration.configuration_type == configuration_type)
        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        StatutoryConfiguration.configuration_type,
                        StatutoryConfiguration.effective_start.desc(),
                    )
                )
            ).all()
        )

    async def create_structure(
        self, actor: User, body: SalaryStructureInput
    ) -> EmployeeSalaryStructure:
        self.require(actor, "payroll.salary_structure.manage")
        employee = await self.employee(actor, body.employee_id)
        overlap = await self.session.scalar(
            select(EmployeeSalaryStructure.id).where(
                EmployeeSalaryStructure.organization_id == actor.organization_id,
                EmployeeSalaryStructure.employee_id == body.employee_id,
                EmployeeSalaryStructure.deleted_at.is_(None),
                EmployeeSalaryStructure.effective_start <= (body.effective_end or date.max),
                or_(
                    EmployeeSalaryStructure.effective_end.is_(None),
                    EmployeeSalaryStructure.effective_end >= body.effective_start,
                ),
            )
        )
        if overlap:
            raise ConflictError("A salary structure already covers these effective dates")
        component_ids = {item.component_id for item in body.items}
        components = list(
            (
                await self.session.scalars(
                    select(SalaryComponent).where(
                        SalaryComponent.organization_id == actor.organization_id,
                        SalaryComponent.id.in_(component_ids),
                        SalaryComponent.deleted_at.is_(None),
                        SalaryComponent.is_active.is_(True),
                    )
                )
            ).all()
        )
        if len(components) != len(component_ids):
            raise NotFoundError("One or more salary components are unavailable")
        component_map = {component.id: component for component in components}
        for line in body.items:
            component = component_map[line.component_id]
            if component.calculation_type == "fixed" and line.amount <= ZERO:
                raise ValidationError(f"{component.name} requires a positive amount")
            if component.calculation_type == "percentage" and line.percentage <= ZERO:
                raise ValidationError(f"{component.name} requires a positive percentage")
        item = EmployeeSalaryStructure(
            organization_id=actor.organization_id,
            created_by_id=actor.id,
            approved_by_id=actor.id if body.status == "active" else None,
            approved_at=datetime.now(UTC) if body.status == "active" else None,
            **body.model_dump(exclude={"items"}),
        )
        self.session.add(item)
        await self.session.flush()
        self.session.add_all(
            [
                SalaryStructureItem(
                    organization_id=actor.organization_id,
                    salary_structure_id=item.id,
                    **line.model_dump(),
                )
                for line in body.items
            ]
        )
        self.audit(
            actor,
            "payroll.salary_structure.created",
            "salary_structure",
            item.id,
            employee_id=str(employee.id),
            effective_start=item.effective_start.isoformat(),
            reason=item.change_reason,
        )
        await self.session.flush()
        return item

    async def preview_structure(self, actor: User, body: SalaryStructureInput) -> dict[str, object]:
        """Calculate a non-persistent compensation preview on the server."""
        self.require(actor, "payroll.salary_structure.manage")
        await self.employee(actor, body.employee_id)
        component_ids = {item.component_id for item in body.items}
        components = list(
            (
                await self.session.scalars(
                    select(SalaryComponent).where(
                        SalaryComponent.organization_id == actor.organization_id,
                        SalaryComponent.id.in_(component_ids),
                        SalaryComponent.deleted_at.is_(None),
                        SalaryComponent.is_active.is_(True),
                        SalaryComponent.effective_start <= body.effective_start,
                        or_(
                            SalaryComponent.effective_end.is_(None),
                            SalaryComponent.effective_end >= body.effective_start,
                        ),
                    )
                )
            ).all()
        )
        if len(components) != len(component_ids):
            raise NotFoundError("One or more salary components are unavailable")
        component_map = {component.id: component for component in components}
        recurring: list[dict[str, object]] = []
        for line in body.items:
            component = component_map[line.component_id]
            if component.calculation_type == "fixed" and line.amount <= ZERO:
                raise ValidationError(f"{component.name} requires a positive amount")
            if component.calculation_type == "percentage" and line.percentage <= ZERO:
                raise ValidationError(f"{component.name} requires a positive percentage")
            recurring.append(
                {
                    "component_id": component.id,
                    "code": component.code,
                    "name": component.name,
                    "component_kind": component.component_kind,
                    "calculation_type": component.calculation_type,
                    "taxable": component.taxable,
                    "pensionable": component.pensionable,
                    "amount": line.amount,
                    "percentage": line.percentage,
                }
            )
        rules = await self.effective_rules(actor, body.effective_start)
        missing = [
            key
            for key, participates in (
                ("paye", body.paye_participates),
                ("pension", body.pension_participates),
                ("nhf", body.nhf_participates),
            )
            if participates and key not in rules
        ]
        if missing:
            raise ValidationError(
                "Missing effective statutory configuration: " + ", ".join(missing)
            )
        output = calculate(
            CalculationInput(
                basic_salary=body.basic_salary,
                recurring_items=recurring,
                adjustments=[],
                loan_deduction=ZERO,
                factor=Decimal("1"),
                paye_rules=rules["paye"].rules if "paye" in rules else None,
                pension_rules=rules["pension"].rules if "pension" in rules else None,
                nhf_rules=rules["nhf"].rules if "nhf" in rules else None,
                paye_participates=body.paye_participates,
                pension_participates=body.pension_participates,
                nhf_participates=body.nhf_participates,
            )
        )
        return {
            "currency": body.currency,
            "basic_salary": output.basic_salary,
            "allowances": output.allowances,
            "gross_pay": output.gross_pay,
            "taxable_pay": output.taxable_pay,
            "paye": output.paye,
            "pension_employee": output.pension_employee,
            "pension_employer": output.pension_employer,
            "nhf": output.nhf,
            "other_deductions": output.other_deductions,
            "total_deductions": output.total_deductions,
            "net_pay": output.net_pay,
            "employer_cost": output.employer_cost,
            "items": self.json_safe(output.items),
            "statutory_snapshot": self.json_safe(output.statutory_snapshot),
        }

    async def end_structure(
        self,
        actor: User,
        structure_id: uuid.UUID,
        effective_end: date,
        reason: str,
    ) -> EmployeeSalaryStructure:
        self.require(actor, "payroll.salary_structure.manage")
        item = await self.session.scalar(
            select(EmployeeSalaryStructure)
            .where(
                EmployeeSalaryStructure.id == structure_id,
                EmployeeSalaryStructure.organization_id == actor.organization_id,
                EmployeeSalaryStructure.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if item is None:
            raise NotFoundError("Salary structure not found")
        if effective_end < item.effective_start:
            raise ValidationError("End date cannot precede the effective date")
        item.effective_end = effective_end
        item.status = "ended"
        self.audit(
            actor,
            "payroll.salary_structure.ended",
            "salary_structure",
            item.id,
            effective_end=effective_end.isoformat(),
            reason=reason,
        )
        return item

    async def list_structures(
        self, actor: User, employee_id: uuid.UUID | None = None
    ) -> list[EmployeeSalaryStructure]:
        self.require(actor, "payroll.salary_structure.view")
        query = select(EmployeeSalaryStructure).where(
            EmployeeSalaryStructure.organization_id == actor.organization_id,
            EmployeeSalaryStructure.deleted_at.is_(None),
        )
        if employee_id:
            await self.employee(actor, employee_id)
            query = query.where(EmployeeSalaryStructure.employee_id == employee_id)
        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        EmployeeSalaryStructure.employee_id,
                        EmployeeSalaryStructure.effective_start.desc(),
                    )
                )
            ).all()
        )

    async def structure_items(
        self, actor: User, structure_id: uuid.UUID
    ) -> list[tuple[SalaryStructureItem, SalaryComponent]]:
        structure = await self.session.scalar(
            select(EmployeeSalaryStructure.id).where(
                EmployeeSalaryStructure.id == structure_id,
                EmployeeSalaryStructure.organization_id == actor.organization_id,
                EmployeeSalaryStructure.deleted_at.is_(None),
            )
        )
        if structure is None:
            raise NotFoundError("Salary structure not found")
        rows = (
            await self.session.execute(
                select(SalaryStructureItem, SalaryComponent)
                .join(SalaryComponent, SalaryComponent.id == SalaryStructureItem.component_id)
                .where(
                    SalaryStructureItem.organization_id == actor.organization_id,
                    SalaryStructureItem.salary_structure_id == structure_id,
                )
                .order_by(SalaryComponent.name)
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def create_period(self, actor: User, body: PayrollPeriodInput) -> PayrollPeriod:
        self.require(actor, "payroll.periods.manage")
        overlap = await self.session.scalar(
            select(PayrollPeriod.id).where(
                PayrollPeriod.organization_id == actor.organization_id,
                PayrollPeriod.start_date <= body.end_date,
                PayrollPeriod.end_date >= body.start_date,
                PayrollPeriod.status != "cancelled",
            )
        )
        if overlap:
            raise ConflictError("A payroll period already covers these dates")
        period = PayrollPeriod(
            organization_id=actor.organization_id,
            created_by_id=actor.id,
            **body.model_dump(),
        )
        self.session.add(period)
        await self.session.flush()
        self.audit(actor, "payroll.period.created", "payroll_period", period.id, name=period.name)
        return period

    async def list_periods(self, actor: User) -> list[PayrollPeriod]:
        self.require(actor, "payroll.periods.view")
        return list(
            (
                await self.session.scalars(
                    select(PayrollPeriod)
                    .where(PayrollPeriod.organization_id == actor.organization_id)
                    .order_by(PayrollPeriod.start_date.desc())
                )
            ).all()
        )

    async def create_adjustment(
        self, actor: User, period_id: uuid.UUID, body: PayrollAdjustmentInput
    ) -> PayrollAdjustment:
        self.require(actor, "payroll.prepare")
        period = await self.period(actor, period_id)
        if period.status not in {"draft", "returned"}:
            raise ValidationError("Adjustments can only be added before payroll review")
        await self.employee(actor, body.employee_id)
        existing = await self.session.scalar(
            select(PayrollAdjustment).where(
                PayrollAdjustment.organization_id == actor.organization_id,
                PayrollAdjustment.idempotency_key == body.idempotency_key,
            )
        )
        if existing:
            return existing
        item = PayrollAdjustment(
            organization_id=actor.organization_id,
            period_id=period.id,
            created_by_id=actor.id,
            approved_by_id=actor.id if body.status == "approved" else None,
            **body.model_dump(),
        )
        self.session.add(item)
        await self.session.flush()
        self.audit(
            actor,
            "payroll.adjustment.created",
            "payroll_adjustment",
            item.id,
            employee_id=str(item.employee_id),
            adjustment_type=item.adjustment_type,
            amount=str(item.amount),
        )
        return item

    async def create_loan(self, actor: User, body: PayrollLoanInput) -> PayrollLoan:
        self.require(actor, "payroll.loans.manage")
        await self.employee(actor, body.employee_id)
        loan = PayrollLoan(
            organization_id=actor.organization_id,
            created_by_id=actor.id,
            outstanding_balance=body.principal,
            **body.model_dump(),
        )
        self.session.add(loan)
        await self.session.flush()
        self.audit(
            actor,
            "payroll.loan.created",
            "payroll_loan",
            loan.id,
            employee_id=str(loan.employee_id),
            principal=str(loan.principal),
        )
        return loan

    async def list_loans(
        self, actor: User, employee_id: uuid.UUID | None = None
    ) -> list[PayrollLoan]:
        self.require(actor, "payroll.loans.manage")
        query = select(PayrollLoan).where(
            PayrollLoan.organization_id == actor.organization_id,
            PayrollLoan.deleted_at.is_(None),
        )
        if employee_id:
            await self.employee(actor, employee_id)
            query = query.where(PayrollLoan.employee_id == employee_id)
        return list(
            (await self.session.scalars(query.order_by(PayrollLoan.created_at.desc()))).all()
        )

    async def effective_rules(
        self, actor: User, on_date: date
    ) -> dict[str, StatutoryConfiguration]:
        rows = list(
            (
                await self.session.scalars(
                    select(StatutoryConfiguration)
                    .where(
                        StatutoryConfiguration.organization_id == actor.organization_id,
                        StatutoryConfiguration.is_active.is_(True),
                        StatutoryConfiguration.effective_start <= on_date,
                        or_(
                            StatutoryConfiguration.effective_end.is_(None),
                            StatutoryConfiguration.effective_end >= on_date,
                        ),
                    )
                    .order_by(StatutoryConfiguration.effective_start.desc())
                )
            ).all()
        )
        result: dict[str, StatutoryConfiguration] = {}
        for row in rows:
            if row.configuration_type in result:
                raise ConflictError(
                    f"Overlapping {row.configuration_type} configurations require correction"
                )
            result[row.configuration_type] = row
        return result

    @staticmethod
    def employee_eligible(employee: User, period: PayrollPeriod) -> bool:
        if employee.status != UserStatus.ACTIVE or employee.removed_at is not None:
            return False
        if employee.employment_start_date and employee.employment_start_date > period.end_date:
            return False
        if employee.employment_end_date and employee.employment_end_date < period.start_date:
            return False
        return employee.employment_status in {"active", "probation", "suspended", "terminated"}

    async def _unpaid_leave_days(
        self, actor: User, employee: User, period: PayrollPeriod
    ) -> Decimal:
        rows = list(
            (
                await self.session.execute(
                    select(LeaveRequest, LeaveType)
                    .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
                    .where(
                        LeaveRequest.organization_id == actor.organization_id,
                        LeaveRequest.employee_id == employee.id,
                        LeaveRequest.status == "approved",
                        LeaveRequest.deleted_at.is_(None),
                        LeaveRequest.start_date <= period.end_date,
                        LeaveRequest.end_date >= period.start_date,
                        LeaveType.is_paid.is_(False),
                    )
                )
            ).all()
        )
        total = ZERO
        for request, _leave_type in rows:
            if request.start_date >= period.start_date and request.end_date <= period.end_date:
                total += request.duration_days
            else:
                overlap_start = max(request.start_date, period.start_date)
                overlap_end = min(request.end_date, period.end_date)
                total += Decimal((overlap_end - overlap_start).days + 1)
        return total

    async def _effective_structure(
        self, actor: User, employee_id: uuid.UUID, on_date: date
    ) -> tuple[EmployeeSalaryStructure | None, int]:
        rows = list(
            (
                await self.session.scalars(
                    select(EmployeeSalaryStructure).where(
                        EmployeeSalaryStructure.organization_id == actor.organization_id,
                        EmployeeSalaryStructure.employee_id == employee_id,
                        EmployeeSalaryStructure.deleted_at.is_(None),
                        EmployeeSalaryStructure.status == "active",
                        EmployeeSalaryStructure.effective_start <= on_date,
                        or_(
                            EmployeeSalaryStructure.effective_end.is_(None),
                            EmployeeSalaryStructure.effective_end >= on_date,
                        ),
                    )
                )
            ).all()
        )
        return (rows[0] if len(rows) == 1 else None, len(rows))

    async def _calculation_inputs(
        self,
        actor: User,
        employee: User,
        period: PayrollPeriod,
        rules: dict[str, StatutoryConfiguration],
        *,
        structures_by_employee: dict[uuid.UUID, list[EmployeeSalaryStructure]] | None = None,
        items_by_structure: (
            dict[uuid.UUID, list[tuple[SalaryStructureItem, SalaryComponent]]] | None
        ) = None,
        adjustments_by_employee: dict[uuid.UUID, list[PayrollAdjustment]] | None = None,
        loans_by_employee: dict[uuid.UUID, list[PayrollLoan]] | None = None,
        unpaid_leave_by_employee: dict[uuid.UUID, Decimal] | None = None,
    ) -> tuple[
        EmployeeSalaryStructure | None,
        CalculationInput | None,
        list[dict[str, object]],
        dict[str, object],
    ]:
        if structures_by_employee is None:
            structure, structure_count = await self._effective_structure(
                actor, employee.id, period.end_date
            )
        else:
            effective_structures = structures_by_employee.get(employee.id, [])
            structure_count = len(effective_structures)
            structure = effective_structures[0] if structure_count == 1 else None
        exceptions: list[dict[str, object]] = []
        if structure_count == 0:
            exceptions.append(
                {"code": "missing_salary_structure", "message": "No effective salary structure"}
            )
        elif structure_count > 1:
            exceptions.append(
                {
                    "code": "overlapping_salary_structures",
                    "message": "Multiple effective salary structures",
                }
            )
        if structure is None:
            return None, None, exceptions, {}
        rows = (
            await self.structure_items(actor, structure.id)
            if items_by_structure is None
            else items_by_structure.get(structure.id, [])
        )
        recurring: list[dict[str, object]] = []
        for line, component in rows:
            if not component.is_active:
                exceptions.append(
                    {"code": "inactive_component", "message": f"{component.name} is inactive"}
                )
                continue
            recurring.append(
                {
                    "component_id": component.id,
                    "code": component.code,
                    "name": component.name,
                    "component_kind": component.component_kind,
                    "calculation_type": component.calculation_type,
                    "taxable": component.taxable,
                    "pensionable": component.pensionable,
                    "amount": line.amount,
                    "percentage": line.percentage,
                }
            )
        adjustments = (
            list(
                (
                    await self.session.scalars(
                        select(PayrollAdjustment).where(
                            PayrollAdjustment.organization_id == actor.organization_id,
                            PayrollAdjustment.period_id == period.id,
                            PayrollAdjustment.employee_id == employee.id,
                            PayrollAdjustment.status == "approved",
                        )
                    )
                ).all()
            )
            if adjustments_by_employee is None
            else adjustments_by_employee.get(employee.id, [])
        )
        loans = (
            list(
                (
                    await self.session.scalars(
                        select(PayrollLoan).where(
                            PayrollLoan.organization_id == actor.organization_id,
                            PayrollLoan.employee_id == employee.id,
                            PayrollLoan.status == "active",
                            PayrollLoan.start_date <= period.end_date,
                            PayrollLoan.outstanding_balance > ZERO,
                            PayrollLoan.deleted_at.is_(None),
                        )
                    )
                ).all()
            )
            if loans_by_employee is None
            else loans_by_employee.get(employee.id, [])
        )
        loan_parts = [
            (loan, min(money(loan.repayment_amount), money(loan.outstanding_balance)))
            for loan in loans
        ]
        policy = rules.get("payroll_policy")
        policy_rules = policy.rules if policy else {"proration_method": "calendar_days"}
        unpaid_leave = (
            await self._unpaid_leave_days(actor, employee, period)
            if unpaid_leave_by_employee is None
            else unpaid_leave_by_employee.get(employee.id, ZERO)
        )
        factor = proration_factor(
            period.start_date,
            period.end_date,
            employee.employment_start_date,
            employee.employment_end_date,
            unpaid_leave,
            policy_rules,
        )
        snapshot: dict[str, object] = {
            "salary_structure_id": str(structure.id),
            "effective_start": structure.effective_start.isoformat(),
            "proration_policy": policy_rules,
            "unpaid_leave_days": str(unpaid_leave),
            "loan_repayments": [
                {"loan_id": str(loan.id), "amount": str(amount)} for loan, amount in loan_parts
            ],
        }
        paye = rules.get("paye")
        pension = rules.get("pension")
        nhf = rules.get("nhf")
        if structure.paye_participates and paye is None:
            exceptions.append(
                {
                    "code": "missing_paye_configuration",
                    "message": "Missing effective PAYE configuration",
                }
            )
        if structure.pension_participates and pension is None:
            exceptions.append(
                {
                    "code": "missing_pension_configuration",
                    "message": "Missing effective pension configuration",
                }
            )
        if structure.nhf_participates and nhf is None:
            exceptions.append(
                {
                    "code": "missing_nhf_configuration",
                    "message": "Missing effective NHF configuration",
                }
            )
        values = CalculationInput(
            basic_salary=structure.basic_salary,
            recurring_items=recurring,
            adjustments=[
                {
                    "adjustment_type": item.adjustment_type,
                    "amount": item.amount,
                    "reason": item.reason,
                }
                for item in adjustments
            ],
            loan_deduction=sum((amount for _loan, amount in loan_parts), ZERO),
            factor=factor,
            paye_rules=paye.rules if paye else None,
            pension_rules=pension.rules if pension else None,
            nhf_rules=nhf.rules if nhf else None,
            paye_participates=structure.paye_participates and paye is not None,
            pension_participates=structure.pension_participates and pension is not None,
            nhf_participates=structure.nhf_participates and nhf is not None,
        )
        return structure, values, exceptions, snapshot

    @staticmethod
    def json_safe(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime, uuid.UUID)):
            return str(value)
        if isinstance(value, dict):
            return {str(key): PayrollService.json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [PayrollService.json_safe(item) for item in value]
        return value

    async def _preload_calculation_data(
        self, actor: User, period: PayrollPeriod, employee_ids: list[uuid.UUID]
    ) -> tuple[
        dict[uuid.UUID, list[EmployeeSalaryStructure]],
        dict[uuid.UUID, list[tuple[SalaryStructureItem, SalaryComponent]]],
        dict[uuid.UUID, list[PayrollAdjustment]],
        dict[uuid.UUID, list[PayrollLoan]],
        dict[uuid.UUID, Decimal],
    ]:
        """Load all per-employee inputs in bounded queries, avoiding Payroll N+1 reads."""
        structures: dict[uuid.UUID, list[EmployeeSalaryStructure]] = defaultdict(list)
        structure_rows = list(
            (
                await self.session.scalars(
                    select(EmployeeSalaryStructure).where(
                        EmployeeSalaryStructure.organization_id == actor.organization_id,
                        EmployeeSalaryStructure.employee_id.in_(employee_ids),
                        EmployeeSalaryStructure.deleted_at.is_(None),
                        EmployeeSalaryStructure.status == "active",
                        EmployeeSalaryStructure.effective_start <= period.end_date,
                        or_(
                            EmployeeSalaryStructure.effective_end.is_(None),
                            EmployeeSalaryStructure.effective_end >= period.end_date,
                        ),
                    )
                )
            ).all()
        )
        for structure in structure_rows:
            structures[structure.employee_id].append(structure)

        items: dict[uuid.UUID, list[tuple[SalaryStructureItem, SalaryComponent]]] = defaultdict(
            list
        )
        structure_ids = [row.id for row in structure_rows]
        if structure_ids:
            item_rows = (
                await self.session.execute(
                    select(SalaryStructureItem, SalaryComponent)
                    .join(SalaryComponent, SalaryComponent.id == SalaryStructureItem.component_id)
                    .where(
                        SalaryStructureItem.organization_id == actor.organization_id,
                        SalaryStructureItem.salary_structure_id.in_(structure_ids),
                    )
                    .order_by(SalaryComponent.name)
                )
            ).all()
            for item, component in item_rows:
                items[item.salary_structure_id].append((item, component))

        adjustments: dict[uuid.UUID, list[PayrollAdjustment]] = defaultdict(list)
        adjustment_rows = list(
            (
                await self.session.scalars(
                    select(PayrollAdjustment).where(
                        PayrollAdjustment.organization_id == actor.organization_id,
                        PayrollAdjustment.period_id == period.id,
                        PayrollAdjustment.employee_id.in_(employee_ids),
                        PayrollAdjustment.status == "approved",
                    )
                )
            ).all()
        )
        for adjustment in adjustment_rows:
            adjustments[adjustment.employee_id].append(adjustment)

        loans: dict[uuid.UUID, list[PayrollLoan]] = defaultdict(list)
        loan_rows = list(
            (
                await self.session.scalars(
                    select(PayrollLoan).where(
                        PayrollLoan.organization_id == actor.organization_id,
                        PayrollLoan.employee_id.in_(employee_ids),
                        PayrollLoan.status == "active",
                        PayrollLoan.start_date <= period.end_date,
                        PayrollLoan.outstanding_balance > ZERO,
                        PayrollLoan.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        for loan in loan_rows:
            loans[loan.employee_id].append(loan)

        unpaid_leave: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
        leave_rows = list(
            (
                await self.session.execute(
                    select(LeaveRequest, LeaveType)
                    .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
                    .where(
                        LeaveRequest.organization_id == actor.organization_id,
                        LeaveRequest.employee_id.in_(employee_ids),
                        LeaveRequest.status == "approved",
                        LeaveRequest.deleted_at.is_(None),
                        LeaveRequest.start_date <= period.end_date,
                        LeaveRequest.end_date >= period.start_date,
                        LeaveType.is_paid.is_(False),
                    )
                )
            ).all()
        )
        for request, _leave_type in leave_rows:
            if request.start_date >= period.start_date and request.end_date <= period.end_date:
                duration = request.duration_days
            else:
                overlap_start = max(request.start_date, period.start_date)
                overlap_end = min(request.end_date, period.end_date)
                duration = Decimal((overlap_end - overlap_start).days + 1)
            unpaid_leave[request.employee_id] += duration
        return structures, items, adjustments, loans, unpaid_leave

    async def prepare(self, actor: User, period_id: uuid.UUID) -> PayrollRun:
        """Rebuild an editable run deterministically without financial side effects."""
        self.require(actor, "payroll.prepare")
        period = await self.period(actor, period_id, lock=True)
        if period.locked or period.status in {"under_review", "approved", "paid", "closed"}:
            raise ValidationError("This payroll period is not editable")
        run = await self.session.scalar(
            select(PayrollRun)
            .where(
                PayrollRun.organization_id == actor.organization_id,
                PayrollRun.period_id == period.id,
            )
            .with_for_update()
        )
        if run is None:
            run = PayrollRun(
                organization_id=actor.organization_id,
                period_id=period.id,
                status="draft",
            )
            self.session.add(run)
            await self.session.flush()
        if run.status not in EDITABLE_RUN:
            raise ValidationError("This payroll run cannot be prepared again")
        result_ids = select(PayrollEmployeeResult.id).where(
            PayrollEmployeeResult.payroll_run_id == run.id
        )
        await self.session.execute(
            delete(PayrollResultItem).where(PayrollResultItem.payroll_result_id.in_(result_ids))
        )
        await self.session.execute(
            delete(PayrollEmployeeResult).where(PayrollEmployeeResult.payroll_run_id == run.id)
        )
        employees = list(
            (
                await self.session.scalars(
                    select(User)
                    .where(
                        User.organization_id == actor.organization_id,
                        User.removed_at.is_(None),
                        User.status == UserStatus.ACTIVE,
                        User.employee_number.is_not(None),
                    )
                    .order_by(User.first_name, User.last_name)
                )
            ).all()
        )
        department_ids = {
            employee.department_id for employee in employees if employee.department_id
        }
        departments = list(
            (
                await self.session.scalars(
                    select(OrganizationUnit).where(
                        OrganizationUnit.organization_id == actor.organization_id,
                        OrganizationUnit.id.in_(department_ids),
                        OrganizationUnit.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        department_names = {department.id: department.name for department in departments}
        employee_ids = [employee.id for employee in employees]
        (
            structures_by_employee,
            items_by_structure,
            adjustments_by_employee,
            loans_by_employee,
            unpaid_leave_by_employee,
        ) = await self._preload_calculation_data(actor, period, employee_ids)
        rules = await self.effective_rules(actor, period.end_date)
        run.rule_snapshot = {
            kind: {
                "id": str(config.id),
                "name": config.name,
                "effective_start": config.effective_start.isoformat(),
                "effective_end": config.effective_end.isoformat() if config.effective_end else None,
                "rules": config.rules,
            }
            for kind, config in rules.items()
        }
        for employee in employees:
            if not self.employee_eligible(employee, period):
                continue
            structure, values, exceptions, snapshot = await self._calculation_inputs(
                actor,
                employee,
                period,
                rules,
                structures_by_employee=structures_by_employee,
                items_by_structure=items_by_structure,
                adjustments_by_employee=adjustments_by_employee,
                loans_by_employee=loans_by_employee,
                unpaid_leave_by_employee=unpaid_leave_by_employee,
            )
            if values is None:
                output = None
            else:
                try:
                    output = calculate(values)
                except ValidationError as error:
                    exceptions.append({"code": "invalid_calculation", "message": str(error)})
                    output = None
            if output and output.net_pay < ZERO:
                exceptions.append({"code": "negative_net_pay", "message": "Net pay is negative"})
            if output and output.net_pay == ZERO:
                exceptions.append({"code": "zero_net_pay", "message": "Net pay is zero"})
            result = PayrollEmployeeResult(
                organization_id=actor.organization_id,
                payroll_run_id=run.id,
                employee_id=employee.id,
                salary_structure_id=structure.id if structure else None,
                employee_name=f"{employee.first_name} {employee.last_name}".strip(),
                employee_number=employee.employee_number,
                department_name=(
                    department_names.get(employee.department_id)
                    if employee.department_id is not None
                    else None
                ),
                job_title=employee.job_title,
                currency=structure.currency if structure else period.currency,
                status="exception" if exceptions else "calculated",
                basic_salary=output.basic_salary if output else ZERO,
                allowances=output.allowances if output else ZERO,
                variable_earnings=output.variable_earnings if output else ZERO,
                gross_pay=output.gross_pay if output else ZERO,
                taxable_pay=output.taxable_pay if output else ZERO,
                paye=output.paye if output else ZERO,
                pension_employee=output.pension_employee if output else ZERO,
                pension_employer=output.pension_employer if output else ZERO,
                nhf=output.nhf if output else ZERO,
                loan_deductions=output.loan_deductions if output else ZERO,
                other_deductions=output.other_deductions if output else ZERO,
                total_deductions=output.total_deductions if output else ZERO,
                net_pay=output.net_pay if output else ZERO,
                employer_cost=output.employer_cost if output else ZERO,
                proration_factor=values.factor if values else ZERO,
                calculation_snapshot=self.json_safe(
                    {**snapshot, "statutory": output.statutory_snapshot if output else {}}
                ),
                exceptions=exceptions,
            )
            self.session.add(result)
            await self.session.flush()
            if output:
                self.session.add_all(
                    [
                        PayrollResultItem(
                            organization_id=actor.organization_id,
                            payroll_result_id=result.id,
                            component_id=item.get("component_id"),
                            code=str(item["code"]),
                            name=str(item["name"]),
                            category=str(item["category"]),
                            amount=Decimal(str(item["amount"])),
                            taxable=bool(item["taxable"]),
                            pensionable=bool(item["pensionable"]),
                            basis=str(item["basis"]),
                            position=position,
                        )
                        for position, item in enumerate(output.items)
                    ]
                )
        now = datetime.now(UTC)
        run.status = "prepared"
        run.version += 1
        run.prepared_by_id = actor.id
        run.prepared_at = now
        run.submitted_by_id = run.approved_by_id = run.returned_by_id = None
        run.submitted_at = run.approved_at = run.returned_at = None
        run.return_reason = None
        period.status = "prepared"
        await self.history(actor, run, "prepared", version=run.version)
        await self.session.flush()
        return run

    async def submit(self, actor: User, run_id: uuid.UUID) -> PayrollRun:
        self.require(actor, "payroll.prepare")
        run = await self.run(actor, run_id, lock=True)
        if run.status != "prepared":
            raise ValidationError("Only prepared payroll can be submitted for review")
        exception_count = await self.session.scalar(
            select(func.count())
            .select_from(PayrollEmployeeResult)
            .where(
                PayrollEmployeeResult.payroll_run_id == run.id,
                PayrollEmployeeResult.status == "exception",
            )
        )
        if exception_count:
            raise ValidationError("Resolve payroll exceptions before review")
        run.status = "under_review"
        run.submitted_by_id = actor.id
        run.submitted_at = datetime.now(UTC)
        period = await self.period(actor, run.period_id)
        period.status = "under_review"
        period.locked = True
        await self.history(actor, run, "submitted_for_review")
        await self.notify_permission(
            actor,
            "payroll.approve",
            "payroll_review_requested",
            f"{period.name} payroll is ready for approval",
            "Review the payroll summary and employee calculations.",
            run,
        )
        return run

    async def return_run(self, actor: User, run_id: uuid.UUID, reason: str) -> PayrollRun:
        self.require(actor, "payroll.review")
        run = await self.run(actor, run_id, lock=True)
        if run.status != "under_review":
            raise ValidationError("Only payroll under review can be returned")
        run.status = "returned"
        run.returned_by_id = actor.id
        run.returned_at = datetime.now(UTC)
        run.return_reason = reason
        period = await self.period(actor, run.period_id)
        period.status = "returned"
        period.locked = False
        await self.history(actor, run, "returned", reason)
        if run.prepared_by_id and run.prepared_by_id != actor.id:
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=run.prepared_by_id,
                notification_type="payroll_returned",
                title=f"{period.name} payroll was returned",
                body=reason,
                category="payroll",
                priority="high",
                metadata={"payroll_run_id": str(run.id)},
                action_url=f"/payroll/runs/{run.id}",
            )
        return run

    async def approve(self, actor: User, run_id: uuid.UUID) -> PayrollRun:
        self.require(actor, "payroll.approve")
        run = await self.run(actor, run_id, lock=True)
        if run.status != "under_review":
            raise ValidationError("Only payroll under review can be approved")
        if run.prepared_by_id == actor.id or run.submitted_by_id == actor.id:
            raise AuthorizationError("Payroll preparers cannot approve their own payroll")
        run.status = "approved"
        run.approved_by_id = actor.id
        run.approved_at = datetime.now(UTC)
        period = await self.period(actor, run.period_id)
        period.status = "approved"
        period.locked = True
        await self.history(actor, run, "approved")
        await self.notify_permission(
            actor,
            "payroll.pay",
            "payroll_approved",
            f"{period.name} payroll is approved",
            "The approved payroll is ready for controlled payment and Finance posting.",
            run,
        )
        return run

    async def pay(
        self, actor: User, run_id: uuid.UUID, body: PayrollPaymentInput
    ) -> PayrollPayment:
        """Atomically post net Payroll and scheduled loan repayments once."""
        self.require(actor, "payroll.pay")
        run = await self.run(actor, run_id, lock=True)
        existing = await self.session.scalar(
            select(PayrollPayment).where(
                PayrollPayment.organization_id == actor.organization_id,
                or_(
                    PayrollPayment.payroll_run_id == run.id,
                    PayrollPayment.idempotency_key == body.idempotency_key,
                ),
            )
        )
        if existing:
            if existing.payroll_run_id != run.id:
                raise ConflictError("Payment idempotency key has already been used")
            return existing
        if run.status != "approved":
            raise ValidationError("Only approved payroll can be paid")
        account = await self.session.scalar(
            select(FinanceAccount)
            .where(
                FinanceAccount.id == body.account_id,
                FinanceAccount.organization_id == actor.organization_id,
                FinanceAccount.deleted_at.is_(None),
                FinanceAccount.status == "active",
            )
            .with_for_update()
        )
        if account is None:
            raise NotFoundError("Finance account not found")
        period = await self.period(actor, run.period_id)
        results = list(
            (
                await self.session.scalars(
                    select(PayrollEmployeeResult).where(
                        PayrollEmployeeResult.organization_id == actor.organization_id,
                        PayrollEmployeeResult.payroll_run_id == run.id,
                    )
                )
            ).all()
        )
        if not results or any(result.status == "exception" for result in results):
            raise ValidationError("Payroll contains unresolved exceptions")
        currencies = {result.currency for result in results}
        if currencies != {account.currency}:
            raise ValidationError("Payroll and payment account currency must match")
        net_total = money(sum((result.net_pay for result in results), ZERO))
        if net_total <= ZERO:
            raise ValidationError("Payroll net payment must be positive")
        reference = f"PAY-{period.start_date:%Y%m}-{str(run.id)[:8].upper()}"
        transaction = FinanceTransaction(
            organization_id=actor.organization_id,
            account_id=account.id,
            voucher_id=None,
            reference=reference,
            idempotency_key=f"payroll:{body.idempotency_key}:net",
            transaction_type="payroll",
            direction="debit",
            amount=net_total,
            currency=account.currency,
            transaction_date=body.payment_date,
            description=f"Net payroll payment · {period.name}",
            payment_method="bank_transfer",
            payment_reference=body.payment_reference,
            beneficiary=f"{len(results)} employees",
            created_by_id=actor.id,
        )
        self.session.add(transaction)
        await self.session.flush()
        payment = PayrollPayment(
            organization_id=actor.organization_id,
            payroll_run_id=run.id,
            account_id=account.id,
            payment_date=body.payment_date,
            payment_reference=body.payment_reference,
            idempotency_key=body.idempotency_key,
            transaction_ids=[str(transaction.id)],
            paid_by_id=actor.id,
        )
        self.session.add(payment)
        for result in results:
            loan_items = result.calculation_snapshot.get("loan_repayments", [])
            if not isinstance(loan_items, list):
                continue
            for raw in loan_items:
                if not isinstance(raw, dict):
                    continue
                loan_id = uuid.UUID(str(raw["loan_id"]))
                amount = money(Decimal(str(raw["amount"])))
                loan = await self.session.scalar(
                    select(PayrollLoan)
                    .where(
                        PayrollLoan.id == loan_id,
                        PayrollLoan.organization_id == actor.organization_id,
                        PayrollLoan.employee_id == result.employee_id,
                    )
                    .with_for_update()
                )
                if loan is None or amount > loan.outstanding_balance:
                    raise ConflictError("A scheduled loan repayment changed after approval")
                repayment = await self.session.scalar(
                    select(PayrollLoanRepayment.id).where(
                        PayrollLoanRepayment.loan_id == loan.id,
                        PayrollLoanRepayment.payroll_result_id == result.id,
                    )
                )
                if repayment:
                    raise ConflictError("Loan repayment has already been posted")
                self.session.add(
                    PayrollLoanRepayment(
                        organization_id=actor.organization_id,
                        loan_id=loan.id,
                        payroll_result_id=result.id,
                        amount=amount,
                    )
                )
                loan.outstanding_balance = money(loan.outstanding_balance - amount)
                if loan.outstanding_balance == ZERO:
                    loan.status = "repaid"
            result.status = "paid"
            result.payslip_generated_at = datetime.now(UTC)
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=result.employee_id,
                notification_type="payslip_available",
                title=f"{period.name} payslip is available",
                body="Your payslip is ready to view and download securely.",
                category="payroll",
                priority="normal",
                metadata={"payroll_result_id": str(result.id)},
                action_url=f"/payroll/my/payslips/{result.id}",
            )
            await self._email_payslip_best_effort(result, period)
        now = datetime.now(UTC)
        run.status = "paid"
        run.paid_by_id = actor.id
        run.paid_at = now
        period.status = "paid"
        period.locked = True
        await self.history(
            actor,
            run,
            "paid",
            payment_reference=body.payment_reference,
            finance_reference=reference,
            amount=str(net_total),
        )
        await self.session.flush()
        return payment

    async def _email_payslip_best_effort(
        self, result: PayrollEmployeeResult, period: PayrollPeriod
    ) -> None:
        """Deliver a secure-link notice without risking the Payroll transaction."""
        try:
            employee = await self.session.scalar(
                select(User).where(
                    User.id == result.employee_id,
                    User.organization_id == result.organization_id,
                    User.removed_at.is_(None),
                )
            )
            if employee is None:
                raise NotFoundError("Payroll notification recipient not found")
            sender = await MeetingEmailSender.for_organization(
                self.session,
                self.notifications.settings,
                result.organization_id,
            )
            rendered = EmailTemplateRegistry.render(
                "payroll.payslip_available",
                PayrollEmailData(
                    payslip_url=(
                        f"{self.notifications.settings.web_app_url.rstrip('/')}/payroll/my"
                    ),
                    period_name=period.name,
                    net_pay=f"{result.net_pay:,.2f}",
                    currency=result.currency,
                ),
                sender.branding,
            )
            transport_id = await sender.send_rendered(
                employee.email,
                rendered,
                message_key=f"payroll-{result.id}-payslip-available",
            )
            self.session.add(
                AuditLog(
                    organization_id=result.organization_id,
                    user_id=None,
                    action=(
                        "payroll.delivery.accepted"
                        if sender.delivery_mode == "smtp"
                        else "payroll.delivery.local_outbox"
                    ),
                    resource="payroll_result",
                    resource_id=result.id,
                    audit_metadata={
                        "event_type": "payroll.payslip_available",
                        "recipient_domain": employee.email.rpartition("@")[2].lower(),
                        "transport_id": transport_id if sender.delivery_mode == "smtp" else None,
                        "template_key": rendered.key,
                        "template_version": rendered.version,
                    },
                )
            )
        except Exception as error:
            self.session.add(
                AuditLog(
                    organization_id=result.organization_id,
                    user_id=None,
                    action="payroll.delivery.failed",
                    resource="payroll_result",
                    resource_id=result.id,
                    audit_metadata={
                        "event_type": "payroll.payslip_available",
                        "error_type": type(error).__name__,
                    },
                )
            )

    async def reverse_payment(
        self, actor: User, run_id: uuid.UUID, body: PayrollReversalInput
    ) -> PayrollPayment:
        self.require(actor, "payroll.pay")
        run = await self.run(actor, run_id, lock=True)
        if run.status != "paid":
            raise ValidationError("Only paid payroll can be reversed")
        payment = await self.session.scalar(
            select(PayrollPayment)
            .where(
                PayrollPayment.organization_id == actor.organization_id,
                PayrollPayment.payroll_run_id == run.id,
                PayrollPayment.reversed_at.is_(None),
            )
            .with_for_update()
        )
        if payment is None:
            raise NotFoundError("Payroll payment not found")
        transaction_ids = [uuid.UUID(value) for value in payment.transaction_ids]
        original = await self.session.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.id.in_(transaction_ids),
            )
        )
        if original is None:
            raise ConflictError("Payroll Finance posting is unavailable")
        existing_reversal = await self.session.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.organization_id == actor.organization_id,
                FinanceTransaction.idempotency_key == f"payroll:{body.idempotency_key}:reversal",
            )
        )
        if existing_reversal:
            return payment
        reversal = FinanceTransaction(
            organization_id=actor.organization_id,
            account_id=original.account_id,
            voucher_id=None,
            reversal_of_id=original.id,
            reference=f"REV-{original.reference}",
            idempotency_key=f"payroll:{body.idempotency_key}:reversal",
            transaction_type="payroll_reversal",
            direction="credit",
            amount=original.amount,
            currency=original.currency,
            transaction_date=date.today(),
            description=f"Payroll reversal · {body.reason}",
            payment_method=original.payment_method,
            payment_reference=original.payment_reference,
            beneficiary=original.beneficiary,
            created_by_id=actor.id,
        )
        self.session.add(reversal)
        repayments = list(
            (
                await self.session.scalars(
                    select(PayrollLoanRepayment)
                    .join(
                        PayrollEmployeeResult,
                        PayrollEmployeeResult.id == PayrollLoanRepayment.payroll_result_id,
                    )
                    .where(
                        PayrollLoanRepayment.organization_id == actor.organization_id,
                        PayrollEmployeeResult.payroll_run_id == run.id,
                        PayrollLoanRepayment.reversed_at.is_(None),
                    )
                )
            ).all()
        )
        for repayment in repayments:
            loan = await self.session.scalar(
                select(PayrollLoan).where(PayrollLoan.id == repayment.loan_id).with_for_update()
            )
            if loan:
                loan.outstanding_balance = money(loan.outstanding_balance + repayment.amount)
                loan.status = "active"
            repayment.reversed_at = datetime.now(UTC)
            repayment.status = "reversed"
        payment.reversed_at = datetime.now(UTC)
        payment.reversed_by_id = actor.id
        payment.reversal_reason = body.reason
        run.status = "approved"
        run.paid_at = None
        run.paid_by_id = None
        period = await self.period(actor, run.period_id)
        period.status = "approved"
        results = list(
            (
                await self.session.scalars(
                    select(PayrollEmployeeResult).where(
                        PayrollEmployeeResult.payroll_run_id == run.id
                    )
                )
            ).all()
        )
        for result in results:
            result.status = "calculated"
        await self.history(actor, run, "payment_reversed", body.reason)
        return payment

    async def close(self, actor: User, run_id: uuid.UUID) -> PayrollRun:
        self.require(actor, "payroll.pay")
        run = await self.run(actor, run_id, lock=True)
        if run.status != "paid":
            raise ValidationError("Only paid payroll can be closed")
        run.status = "closed"
        run.closed_at = datetime.now(UTC)
        period = await self.period(actor, run.period_id)
        period.status = "closed"
        period.locked = True
        await self.history(actor, run, "closed")
        return run

    async def own_result(self, actor: User, result_id: uuid.UUID) -> PayrollEmployeeResult:
        self.require(actor, "payroll.view_own")
        row = await self.session.scalar(
            select(PayrollEmployeeResult).where(
                PayrollEmployeeResult.id == result_id,
                PayrollEmployeeResult.organization_id == actor.organization_id,
                PayrollEmployeeResult.employee_id == actor.id,
                PayrollEmployeeResult.status == "paid",
            )
        )
        if row is None:
            raise NotFoundError("Payslip not found")
        return row

    async def authorized_result(self, actor: User, result_id: uuid.UUID) -> PayrollEmployeeResult:
        query = select(PayrollEmployeeResult).where(
            PayrollEmployeeResult.id == result_id,
            PayrollEmployeeResult.organization_id == actor.organization_id,
        )
        if not self.has(actor, "payroll.view_employee"):
            query = query.where(PayrollEmployeeResult.employee_id == actor.id)
        row = await self.session.scalar(query)
        if row is None:
            raise NotFoundError("Payroll result not found")
        return row

    async def result_items(
        self, actor: User, result: PayrollEmployeeResult
    ) -> list[PayrollResultItem]:
        return list(
            (
                await self.session.scalars(
                    select(PayrollResultItem)
                    .where(
                        PayrollResultItem.organization_id == actor.organization_id,
                        PayrollResultItem.payroll_result_id == result.id,
                    )
                    .order_by(PayrollResultItem.position)
                )
            ).all()
        )
