"""Permission-first Payroll HTTP boundary."""

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.payroll import documents
from meetinghq_api.modules.payroll.models import PayrollRun
from meetinghq_api.modules.payroll.queries import PayrollQueries
from meetinghq_api.modules.payroll.schemas import (
    PayrollAdjustmentInput,
    PayrollLoanInput,
    PayrollLoanResponse,
    PayrollPaymentInput,
    PayrollPaymentResponse,
    PayrollPeriodInput,
    PayrollPeriodResponse,
    PayrollReportRow,
    PayrollResultFilters,
    PayrollResultResponse,
    PayrollReturnInput,
    PayrollReversalInput,
    PayrollRunDetail,
    PayrollRunResponse,
    SalaryComponentInput,
    SalaryComponentResponse,
    SalaryPreviewResponse,
    SalaryStructureEndInput,
    SalaryStructureInput,
    SalaryStructureResponse,
    StatutoryConfigurationInput,
    StatutoryConfigurationResponse,
)
from meetinghq_api.modules.payroll.service import PayrollService
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/payroll", tags=["payroll"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def service(session: Session, settings: AppSettings) -> PayrollService:
    return PayrollService(session, NotificationService(session, settings))


def download(data: bytes, filename: str, media_type: str) -> Response:
    return Response(
        data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/components", response_model=list[SalaryComponentResponse])
async def list_components(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.view")],
    active: bool | None = None,
) -> list[SalaryComponentResponse]:
    return [
        SalaryComponentResponse.model_validate(row)
        for row in await service(session, settings).list_components(user, active=active)
    ]


@router.post("/components", response_model=SalaryComponentResponse, status_code=201)
async def create_component(
    body: SalaryComponentInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.components.manage")],
) -> SalaryComponentResponse:
    return SalaryComponentResponse.model_validate(
        await service(session, settings).create_component(user, body)
    )


@router.put("/components/{component_id}", response_model=SalaryComponentResponse)
async def update_component(
    component_id: uuid.UUID,
    body: SalaryComponentInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.components.manage")],
) -> SalaryComponentResponse:
    return SalaryComponentResponse.model_validate(
        await service(session, settings).update_component(user, component_id, body)
    )


@router.get("/salary-structures", response_model=list[SalaryStructureResponse])
async def list_structures(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.view")],
    employee_id: uuid.UUID | None = None,
) -> list[SalaryStructureResponse]:
    svc = service(session, settings)
    query = PayrollQueries(svc)
    return [
        await query.structure_response(user, row)
        for row in await svc.list_structures(user, employee_id)
    ]


@router.post("/salary-structures", response_model=SalaryStructureResponse, status_code=201)
async def create_structure(
    body: SalaryStructureInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.manage")],
) -> SalaryStructureResponse:
    svc = service(session, settings)
    return await PayrollQueries(svc).structure_response(
        user, await svc.create_structure(user, body)
    )


@router.post("/salary-structures/preview", response_model=SalaryPreviewResponse)
async def preview_structure(
    body: SalaryStructureInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.manage")],
) -> SalaryPreviewResponse:
    return SalaryPreviewResponse.model_validate(
        await service(session, settings).preview_structure(user, body)
    )


@router.post("/salary-structures/{structure_id}/end", response_model=SalaryStructureResponse)
async def end_structure(
    structure_id: uuid.UUID,
    body: SalaryStructureEndInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.manage")],
) -> SalaryStructureResponse:
    svc = service(session, settings)
    row = await svc.end_structure(user, structure_id, body.effective_end, body.reason)
    return await PayrollQueries(svc).structure_response(user, row)


@router.get("/statutory", response_model=list[StatutoryConfigurationResponse])
async def list_statutory(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.salary_structure.view")],
    configuration_type: str | None = None,
) -> list[StatutoryConfigurationResponse]:
    return [
        StatutoryConfigurationResponse.model_validate(row)
        for row in await service(session, settings).list_statutory(user, configuration_type)
    ]


@router.post("/statutory", response_model=StatutoryConfigurationResponse, status_code=201)
async def create_statutory(
    body: StatutoryConfigurationInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.statutory.manage")],
) -> StatutoryConfigurationResponse:
    return StatutoryConfigurationResponse.model_validate(
        await service(session, settings).create_statutory(user, body)
    )


@router.get("/periods", response_model=list[PayrollPeriodResponse])
async def list_periods(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.periods.view")],
) -> list[PayrollPeriodResponse]:
    return [
        PayrollPeriodResponse.model_validate(row)
        for row in await service(session, settings).list_periods(user)
    ]


@router.post("/periods", response_model=PayrollPeriodResponse, status_code=201)
async def create_period(
    body: PayrollPeriodInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.periods.manage")],
) -> PayrollPeriodResponse:
    return PayrollPeriodResponse.model_validate(
        await service(session, settings).create_period(user, body)
    )


@router.post("/periods/{period_id}/adjustments", status_code=201)
async def create_adjustment(
    period_id: uuid.UUID,
    body: PayrollAdjustmentInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.prepare")],
) -> dict[str, object]:
    row = await service(session, settings).create_adjustment(user, period_id, body)
    return {"id": str(row.id), "status": row.status, "amount": str(row.amount)}


@router.post("/loans", response_model=PayrollLoanResponse, status_code=201)
async def create_loan(
    body: PayrollLoanInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.loans.manage")],
) -> PayrollLoanResponse:
    return PayrollLoanResponse.model_validate(
        await service(session, settings).create_loan(user, body)
    )


@router.get("/loans", response_model=list[PayrollLoanResponse])
async def list_loans(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.loans.manage")],
    employee_id: uuid.UUID | None = None,
) -> list[PayrollLoanResponse]:
    return [
        PayrollLoanResponse.model_validate(row)
        for row in await service(session, settings).list_loans(user, employee_id)
    ]


@router.post("/periods/{period_id}/prepare", response_model=PayrollRunResponse)
async def prepare(
    period_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.prepare")],
) -> PayrollRunResponse:
    return PayrollRunResponse.model_validate(
        await service(session, settings).prepare(user, period_id)
    )


@router.get("/runs", response_model=list[PayrollRunResponse])
async def list_runs(
    session: Session,
    user: Annotated[User, require_permission("payroll.periods.view")],
) -> list[PayrollRunResponse]:
    rows = list(
        (
            await session.scalars(
                select(PayrollRun)
                .where(PayrollRun.organization_id == user.organization_id)
                .order_by(PayrollRun.created_at.desc())
            )
        ).all()
    )
    return [PayrollRunResponse.model_validate(row) for row in rows]


@router.get("/runs/{run_id}", response_model=PayrollRunDetail)
async def run_detail(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.periods.view")],
    filters: Annotated[PayrollResultFilters, Query()],
) -> PayrollRunDetail:
    return await PayrollQueries(service(session, settings)).detail(user, run_id, filters)


@router.post("/runs/{run_id}/submit", response_model=PayrollRunResponse)
async def submit_run(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.prepare")],
) -> PayrollRunResponse:
    return PayrollRunResponse.model_validate(await service(session, settings).submit(user, run_id))


@router.post("/runs/{run_id}/return", response_model=PayrollRunResponse)
async def return_run(
    run_id: uuid.UUID,
    body: PayrollReturnInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.review")],
) -> PayrollRunResponse:
    return PayrollRunResponse.model_validate(
        await service(session, settings).return_run(user, run_id, body.reason)
    )


@router.post("/runs/{run_id}/approve", response_model=PayrollRunResponse)
async def approve_run(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.approve")],
) -> PayrollRunResponse:
    return PayrollRunResponse.model_validate(await service(session, settings).approve(user, run_id))


@router.post("/runs/{run_id}/pay", response_model=PayrollPaymentResponse)
async def pay_run(
    run_id: uuid.UUID,
    body: PayrollPaymentInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.pay")],
) -> PayrollPaymentResponse:
    return PayrollPaymentResponse.model_validate(
        await service(session, settings).pay(user, run_id, body)
    )


@router.post("/runs/{run_id}/reverse", response_model=PayrollPaymentResponse)
async def reverse_run(
    run_id: uuid.UUID,
    body: PayrollReversalInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.pay")],
) -> PayrollPaymentResponse:
    return PayrollPaymentResponse.model_validate(
        await service(session, settings).reverse_payment(user, run_id, body)
    )


@router.post("/runs/{run_id}/close", response_model=PayrollRunResponse)
async def close_run(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.pay")],
) -> PayrollRunResponse:
    return PayrollRunResponse.model_validate(await service(session, settings).close(user, run_id))


@router.get("/results/{result_id}", response_model=PayrollResultResponse)
async def result_detail(
    result_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.view_own")],
) -> PayrollResultResponse:
    svc = service(session, settings)
    return await PayrollQueries(svc).result_response(
        user, await svc.authorized_result(user, result_id)
    )


@router.get("/my/payslips", response_model=list[PayrollResultResponse])
async def my_payslips(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.view_own")],
) -> list[PayrollResultResponse]:
    svc = service(session, settings)
    return await PayrollQueries(svc).own_payslips(user)


async def payslip_bytes(svc: PayrollService, user: User, result_id: uuid.UUID) -> tuple[bytes, str]:
    result = await svc.authorized_result(user, result_id)
    if result.status != "paid":
        from meetinghq_api.shared.exceptions import ValidationError

        raise ValidationError("Payslips are available only after payment")
    response = await PayrollQueries(svc).result_response(user, result)
    run = await svc.run(user, result.payroll_run_id)
    period = await svc.period(user, run.period_id)
    organization = await svc.session.scalar(
        select(Organization).where(Organization.id == user.organization_id)
    )
    data = await asyncio.to_thread(
        documents.payslip_pdf,
        response,
        organization.name if organization else "MeetingHQ",
        period.name,
    )
    svc.audit(user, "payroll.payslip.downloaded", "payroll_result", result.id)
    return data, f"payslip-{period.start_date:%Y-%m}.pdf"


@router.get("/results/{result_id}/payslip")
async def download_payslip(
    result_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.payslip.download_own")],
) -> Response:
    data, filename = await payslip_bytes(service(session, settings), user, result_id)
    return download(data, filename, "application/pdf")


@router.get("/runs/{run_id}/reports", response_model=list[PayrollReportRow])
async def reports(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.reports.view")],
) -> list[PayrollReportRow]:
    return await PayrollQueries(service(session, settings)).report(user, run_id)


@router.get("/runs/{run_id}/export")
async def export_register(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.export")],
) -> Response:
    svc = service(session, settings)
    page = await PayrollQueries(svc).result_page(
        user, run_id, PayrollResultFilters(page=1, page_size=100)
    )
    return download(documents.payroll_register_csv(page.items), "payroll-register.csv", "text/csv")


@router.get("/runs/{run_id}/statutory-export")
async def export_statutory(
    run_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("payroll.export")],
) -> Response:
    rows = await PayrollQueries(service(session, settings)).report(user, run_id)
    return download(documents.statutory_summary_csv(rows), "payroll-statutory.csv", "text/csv")
