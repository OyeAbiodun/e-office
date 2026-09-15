"""Reporting & Management Intelligence HTTP boundary."""

import asyncio
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import (
    CurrentUser,
    require_any_permission,
    require_permission,
)
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.reports import exports
from meetinghq_api.modules.reports.schemas import (
    GenerateReportInput,
    NarrativeUpdate,
    PolicyResponse,
    PolicyUpdate,
    ReportDetail,
    ReportingDashboard,
    ReportPage,
    ReportResponse,
    ReviewInput,
)
from meetinghq_api.modules.reports.service import ReportingService
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/reports", tags=["reporting"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
ReportReader = Annotated[
    User,
    require_any_permission(
        "reports.view_own",
        "reports.view_team",
        "reports.view_department",
        "reports.view_management",
        "projects.view_reports",
    ),
]


def service(session: Session, settings: AppSettings) -> ReportingService:
    return ReportingService(session, NotificationService(session, settings))


@router.get("/policy", response_model=PolicyResponse)
async def get_policy(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.manage_policy")],
) -> PolicyResponse:
    return await service(session, settings).policy(user)


@router.put("/policy", response_model=PolicyResponse)
async def update_policy(
    body: PolicyUpdate,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.manage_policy")],
) -> PolicyResponse:
    return await service(session, settings).update_policy(user, body)


@router.get("/dashboard", response_model=ReportingDashboard)
async def dashboard(
    session: Session, settings: AppSettings, user: ReportReader
) -> ReportingDashboard:
    return await service(session, settings).dashboard(user)


@router.get("/source-preview")
async def source_preview(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.view_own")],
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    return await service(session, settings).preview_sources(user, start_date, end_date)


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    body: GenerateReportInput,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> ReportResponse:
    return await service(session, settings).generate(user, body)


@router.post("/scheduler/run")
async def run_scheduler(
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.manage_policy")],
) -> dict[str, int]:
    generated = await service(session, settings).process_scheduled_reports(force_generation=True)
    return {"generated": generated}


@router.get("", response_model=ReportPage)
async def list_reports(
    session: Session,
    settings: AppSettings,
    user: ReportReader,
    search: str | None = Query(default=None, max_length=160),
    report_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    period_type: str | None = None,
    report_status: str | None = Query(default=None, alias="status"),
    period_start: date | None = None,
    period_end: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> ReportPage:
    return await service(session, settings).list_reports(
        user,
        search=search,
        report_type=report_type,
        subject_id=subject_id,
        period_type=period_type,
        status=report_status,
        period_start=period_start,
        period_end=period_end,
        page=page,
        page_size=page_size,
    )


@router.get("/{report_id}", response_model=ReportDetail)
async def report_detail(
    report_id: uuid.UUID, session: Session, settings: AppSettings, user: ReportReader
) -> ReportDetail:
    return await service(session, settings).detail(user, report_id)


@router.patch("/{report_id}", response_model=ReportResponse)
async def edit_report(
    report_id: uuid.UUID,
    body: NarrativeUpdate,
    session: Session,
    settings: AppSettings,
    user: CurrentUser,
) -> ReportResponse:
    return await service(session, settings).edit(user, report_id, body)


@router.post("/{report_id}/submit", response_model=ReportResponse)
async def submit_report(
    report_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.submit_own")],
) -> ReportResponse:
    return await service(session, settings).submit(user, report_id)


@router.post("/{report_id}/review", response_model=ReportResponse)
async def review_report(
    report_id: uuid.UUID,
    body: ReviewInput,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.review_team")],
) -> ReportResponse:
    return await service(session, settings).review(user, report_id, body)


@router.get("/{report_id}/export")
async def export_report(
    report_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("reports.export")],
    format: Literal["pdf", "csv", "xlsx"] = "pdf",
) -> Response:
    reporting = service(session, settings)
    report = (await reporting.detail(user, report_id)).report
    organization = await session.get(Organization, user.organization_id)
    if format == "csv":
        data = exports.report_csv(report)
        content_type = "text/csv"
        suffix = "csv"
    elif format == "xlsx":
        data = exports.report_xlsx(report)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        suffix = "xlsx"
    else:
        data = await asyncio.to_thread(
            exports.report_pdf, report, organization.name if organization else "OfficeFlow"
        )
        content_type = "application/pdf"
        suffix = "pdf"
    await reporting._event(
        user.organization_id,
        user.id,
        "report.exported",
        report.id,
        {"format": suffix},
    )
    return Response(
        data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="report-{report.id}.{suffix}"'},
    )
