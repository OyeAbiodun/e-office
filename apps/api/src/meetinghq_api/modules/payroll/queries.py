"""Tenant-scoped Payroll read projections and reporting."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import asc, case, desc, func, or_, select

from meetinghq_api.modules.payroll.models import (
    EmployeeSalaryStructure,
    PayrollEmployeeResult,
    PayrollHistory,
    PayrollPeriod,
    PayrollResultItem,
    PayrollRun,
)
from meetinghq_api.modules.payroll.schemas import (
    PayrollPeriodResponse,
    PayrollReportRow,
    PayrollResultFilters,
    PayrollResultItemResponse,
    PayrollResultPage,
    PayrollResultResponse,
    PayrollRunDetail,
    PayrollRunResponse,
    PayrollSummary,
    SalaryStructureItemResponse,
    SalaryStructureResponse,
)
from meetinghq_api.modules.payroll.service import PayrollService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError

ZERO = Decimal("0.00")


class PayrollQueries:
    def __init__(self, service: PayrollService) -> None:
        self.service = service
        self.session = service.session

    async def structure_response(
        self, actor: User, structure: EmployeeSalaryStructure
    ) -> SalaryStructureResponse:
        # Resolve names with explicit tenant-scoped queries; never disclose foreign users.
        employee_row = await self.session.scalar(
            select(User).where(
                User.id == structure.employee_id,
                User.organization_id == actor.organization_id,
            )
        )
        changed_by = await self.session.scalar(
            select(User).where(
                User.id == structure.created_by_id,
                User.organization_id == actor.organization_id,
            )
        )
        item_rows = await self.service.structure_items(actor, structure.id)
        items = [
            SalaryStructureItemResponse.model_validate(line).model_copy(
                update={
                    "component_code": component.code,
                    "component_name": component.name,
                    "component_kind": component.component_kind,
                }
            )
            for line, component in item_rows
        ]
        gross = structure.basic_salary + sum(
            (
                (
                    line.amount
                    if component.calculation_type == "fixed"
                    else structure.basic_salary * line.percentage / Decimal("100")
                )
                for line, component in item_rows
                if component.component_kind == "earning"
            ),
            ZERO,
        )
        return SalaryStructureResponse.model_validate(structure).model_copy(
            update={
                "employee_name": (
                    f"{employee_row.first_name} {employee_row.last_name}".strip()
                    if employee_row
                    else None
                ),
                "changed_by_name": (
                    f"{changed_by.first_name} {changed_by.last_name}".strip()
                    if changed_by
                    else None
                ),
                "gross_salary": gross,
                "items": items,
            }
        )

    async def result_response(
        self, actor: User, result: PayrollEmployeeResult
    ) -> PayrollResultResponse:
        return (await self.result_responses(actor, [result]))[0]

    async def result_responses(
        self, actor: User, results: list[PayrollEmployeeResult]
    ) -> list[PayrollResultResponse]:
        """Build result projections with two bulk queries, avoiding per-employee loading."""
        if not results:
            return []
        result_ids = [row.id for row in results]
        item_rows = list(
            (
                await self.session.scalars(
                    select(PayrollResultItem)
                    .where(
                        PayrollResultItem.organization_id == actor.organization_id,
                        PayrollResultItem.payroll_result_id.in_(result_ids),
                    )
                    .order_by(PayrollResultItem.position, PayrollResultItem.id)
                )
            ).all()
        )
        items_by_result: dict[uuid.UUID, list[PayrollResultItemResponse]] = {}
        for item in item_rows:
            items_by_result.setdefault(item.payroll_result_id, []).append(
                PayrollResultItemResponse.model_validate(item)
            )
        run_ids = {row.payroll_run_id for row in results}
        period_rows = (
            await self.session.execute(
                select(
                    PayrollRun.id,
                    PayrollPeriod.name,
                    PayrollPeriod.start_date,
                    PayrollPeriod.end_date,
                    PayrollPeriod.payment_date,
                )
                .join(PayrollPeriod, PayrollPeriod.id == PayrollRun.period_id)
                .where(
                    PayrollRun.organization_id == actor.organization_id,
                    PayrollPeriod.organization_id == actor.organization_id,
                    PayrollRun.id.in_(run_ids),
                )
            )
        ).all()
        periods = {
            row[0]: {
                "period_name": row[1],
                "period_start": row[2],
                "period_end": row[3],
                "payment_date": row[4],
            }
            for row in period_rows
        }
        return [
            PayrollResultResponse.model_validate(result).model_copy(
                update={
                    "items": items_by_result.get(result.id, []),
                    **periods.get(result.payroll_run_id, {}),
                }
            )
            for result in results
        ]

    async def result_page(
        self, actor: User, run_id: uuid.UUID, filters: PayrollResultFilters
    ) -> PayrollResultPage:
        await self.service.run(actor, run_id)
        query = select(PayrollEmployeeResult).where(
            PayrollEmployeeResult.organization_id == actor.organization_id,
            PayrollEmployeeResult.payroll_run_id == run_id,
        )
        if filters.employee_id:
            await self.service.employee(actor, filters.employee_id)
            query = query.where(PayrollEmployeeResult.employee_id == filters.employee_id)
        if filters.department_id:
            # Results intentionally snapshot names; resolve canonical department to its name.
            from meetinghq_api.modules.organizations.models import OrganizationUnit

            department = await self.session.scalar(
                select(OrganizationUnit).where(
                    OrganizationUnit.id == filters.department_id,
                    OrganizationUnit.organization_id == actor.organization_id,
                )
            )
            if department is None:
                raise NotFoundError("Department not found")
            query = query.where(PayrollEmployeeResult.department_name == department.name)
        if filters.exception_only:
            query = query.where(PayrollEmployeeResult.status == "exception")
        if filters.payment_status:
            query = query.where(PayrollEmployeeResult.status == filters.payment_status)
        if filters.search:
            pattern = f"%{filters.search}%"
            query = query.where(
                or_(
                    PayrollEmployeeResult.employee_name.ilike(pattern),
                    PayrollEmployeeResult.employee_number.ilike(pattern),
                    PayrollEmployeeResult.department_name.ilike(pattern),
                )
            )
        ordering = {
            "employee": PayrollEmployeeResult.employee_name,
            "gross": PayrollEmployeeResult.gross_pay,
            "net": PayrollEmployeeResult.net_pay,
            "department": PayrollEmployeeResult.department_name,
            "status": PayrollEmployeeResult.status,
        }[filters.sort]
        query = query.order_by(
            desc(ordering) if filters.direction == "desc" else asc(ordering),
            PayrollEmployeeResult.id,
        )
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
                )
            ).all()
        )
        return PayrollResultPage(
            items=await self.result_responses(actor, rows),
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    async def summary(self, actor: User, run_id: uuid.UUID) -> PayrollSummary:
        await self.service.run(actor, run_id)
        row = (
            await self.session.execute(
                select(
                    func.count(PayrollEmployeeResult.id),
                    func.sum(case((PayrollEmployeeResult.status == "exception", 1), else_=0)),
                    func.max(PayrollEmployeeResult.currency),
                    func.sum(PayrollEmployeeResult.gross_pay),
                    func.sum(PayrollEmployeeResult.paye),
                    func.sum(PayrollEmployeeResult.pension_employee),
                    func.sum(PayrollEmployeeResult.pension_employer),
                    func.sum(PayrollEmployeeResult.nhf),
                    func.sum(PayrollEmployeeResult.loan_deductions),
                    func.sum(PayrollEmployeeResult.other_deductions),
                    func.sum(PayrollEmployeeResult.total_deductions),
                    func.sum(PayrollEmployeeResult.net_pay),
                    func.sum(PayrollEmployeeResult.employer_cost),
                ).where(
                    PayrollEmployeeResult.organization_id == actor.organization_id,
                    PayrollEmployeeResult.payroll_run_id == run_id,
                )
            )
        ).one()
        values = [value or ZERO for value in row[3:]]
        return PayrollSummary(
            employee_count=int(row[0] or 0),
            exception_count=int(row[1] or 0),
            currency=row[2] or "NGN",
            gross_payroll=values[0],
            paye=values[1],
            pension_employee=values[2],
            pension_employer=values[3],
            nhf=values[4],
            loan_deductions=values[5],
            other_deductions=values[6],
            total_deductions=values[7],
            net_payroll=values[8],
            employer_cost=values[9],
        )

    async def detail(
        self, actor: User, run_id: uuid.UUID, filters: PayrollResultFilters
    ) -> PayrollRunDetail:
        self.service.require(actor, "payroll.periods.view")
        run = await self.service.run(actor, run_id)
        period = await self.service.period(actor, run.period_id)
        history = list(
            (
                await self.session.scalars(
                    select(PayrollHistory)
                    .where(
                        PayrollHistory.organization_id == actor.organization_id,
                        PayrollHistory.payroll_run_id == run.id,
                    )
                    .order_by(PayrollHistory.created_at.desc())
                )
            ).all()
        )
        permissions = self.service.permissions(actor)
        actions: list[str] = []
        if "payroll.prepare" in permissions and run.status in {"draft", "returned", "prepared"}:
            actions.extend(["prepare", "submit"])
        if "payroll.review" in permissions and run.status == "under_review":
            actions.append("return")
        if "payroll.approve" in permissions and run.status == "under_review":
            actions.append("approve")
        if "payroll.pay" in permissions and run.status == "approved":
            actions.append("pay")
        if "payroll.pay" in permissions and run.status == "paid":
            actions.extend(["reverse", "close"])
        return PayrollRunDetail(
            run=PayrollRunResponse.model_validate(run),
            period=PayrollPeriodResponse.model_validate(period),
            summary=await self.summary(actor, run.id),
            results=await self.result_page(actor, run.id, filters),
            history=[
                {
                    "id": str(item.id),
                    "actor_id": str(item.actor_id) if item.actor_id else None,
                    "event_type": item.event_type,
                    "reason": item.reason,
                    "payload": item.payload,
                    "created_at": item.created_at.isoformat(),
                }
                for item in history
            ],
            allowed_actions=actions,
        )

    async def own_payslips(self, actor: User) -> list[PayrollResultResponse]:
        self.service.require(actor, "payroll.view_own")
        rows = list(
            (
                await self.session.scalars(
                    select(PayrollEmployeeResult)
                    .where(
                        PayrollEmployeeResult.organization_id == actor.organization_id,
                        PayrollEmployeeResult.employee_id == actor.id,
                        PayrollEmployeeResult.status == "paid",
                    )
                    .order_by(PayrollEmployeeResult.created_at.desc())
                )
            ).all()
        )
        return await self.result_responses(actor, rows)

    async def report(self, actor: User, run_id: uuid.UUID) -> list[PayrollReportRow]:
        self.service.require(actor, "payroll.reports.view")
        await self.service.run(actor, run_id)
        rows = (
            await self.session.execute(
                select(
                    PayrollEmployeeResult.department_name,
                    func.count(PayrollEmployeeResult.id),
                    func.sum(PayrollEmployeeResult.gross_pay),
                    func.sum(PayrollEmployeeResult.paye),
                    func.sum(PayrollEmployeeResult.pension_employee),
                    func.sum(PayrollEmployeeResult.nhf),
                    func.sum(PayrollEmployeeResult.total_deductions),
                    func.sum(PayrollEmployeeResult.net_pay),
                    func.sum(PayrollEmployeeResult.employer_cost),
                )
                .where(
                    PayrollEmployeeResult.organization_id == actor.organization_id,
                    PayrollEmployeeResult.payroll_run_id == run_id,
                )
                .group_by(PayrollEmployeeResult.department_name)
                .order_by(PayrollEmployeeResult.department_name)
            )
        ).all()
        return [
            PayrollReportRow(
                group=row[0] or "Unassigned",
                employee_count=int(row[1]),
                gross_pay=row[2] or ZERO,
                paye=row[3] or ZERO,
                pension=row[4] or ZERO,
                nhf=row[5] or ZERO,
                deductions=row[6] or ZERO,
                net_pay=row[7] or ZERO,
                employer_cost=row[8] or ZERO,
            )
            for row in rows
        ]
