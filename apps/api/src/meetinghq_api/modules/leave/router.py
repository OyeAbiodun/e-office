"""Leave Management HTTP boundary."""

import asyncio
import csv
import io
import uuid
from datetime import date
from enum import IntEnum
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.leave.schemas import (
    AdjustmentInput,
    AdjustmentResponse,
    BalanceListItem,
    BalancePage,
    BalanceResponse,
    ControlledAdjustmentInput,
    EntitlementInput,
    EntitlementResponse,
    LeaveAttachmentResponse,
    LeaveAvailabilityItem,
    LeavePeriodInput,
    LeavePeriodResponse,
    LeaveReportRow,
    LeaveRequestDetail,
    LeaveRequestInput,
    LeaveRequestPage,
    LeaveRequestResponse,
    LeaveStatusSummary,
    LeaveSummaryResponse,
    LeaveTypeInput,
    LeaveTypeResponse,
    LedgerPage,
    ManagerLeaveSummary,
    PeriodStatusInput,
    RejectInput,
    ReviewInput,
    WorkingDayPreview,
    WorkingDayResult,
    WorkingWeekInput,
    WorkingWeekResponse,
)
from meetinghq_api.modules.leave.service import LeaveService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/leave", tags=["leave"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
LeaveUpload = Annotated[UploadFile, File()]
ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class LeavePageSize(IntEnum):
    TEN = 10
    TWENTY_FIVE = 25
    FIFTY = 50
    ONE_HUNDRED = 100


def _attachment_path(storage_root: str, storage_key: str) -> Path | None:
    root = Path(storage_root).resolve()
    target = (root / storage_key).resolve()
    return target if root in target.parents and target.is_file() else None


@router.get("/types", response_model=list[LeaveTypeResponse])
async def list_types(
    session: Session,
    user: Annotated[User, require_permission("leave.types.view")],
    search: str | None = Query(default=None, max_length=120),
    active: bool | None = None,
) -> list[LeaveTypeResponse]:
    return [
        LeaveTypeResponse.model_validate(v)
        for v in await LeaveService(session).list_types(user, search=search, active=active)
    ]


@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_type(
    body: LeaveTypeInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(await LeaveService(session).create_type(user, body))


@router.put("/types/{type_id}", response_model=LeaveTypeResponse)
async def update_type(
    type_id: uuid.UUID,
    body: LeaveTypeInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await LeaveService(session).update_type(user, type_id, body)
    )


@router.patch("/types/{type_id}/active", response_model=LeaveTypeResponse)
async def set_type_active(
    type_id: uuid.UUID,
    active: bool,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(
        await LeaveService(session).set_type_active(user, type_id, active)
    )


@router.get("/periods", response_model=list[LeavePeriodResponse])
async def list_periods(
    session: Session, user: Annotated[User, require_permission("leave.types.view")]
) -> list[LeavePeriodResponse]:
    return [
        LeavePeriodResponse.model_validate(v)
        for v in await LeaveService(session).list_periods(user)
    ]


@router.post("/periods", response_model=LeavePeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_period(
    body: LeavePeriodInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeavePeriodResponse:
    return LeavePeriodResponse.model_validate(await LeaveService(session).create_period(user, body))


@router.get("/periods/current", response_model=LeavePeriodResponse)
async def current_period(
    session: Session,
    user: Annotated[User, require_permission("leave.types.view")],
    on_date: date | None = None,
) -> LeavePeriodResponse:
    return LeavePeriodResponse.model_validate(
        await LeaveService(session).current_period(user, on_date)
    )


@router.get("/periods/{period_id}", response_model=LeavePeriodResponse)
async def period_detail(
    period_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.types.view")],
) -> LeavePeriodResponse:
    return LeavePeriodResponse.model_validate(
        await LeaveService(session).period_detail(user, period_id)
    )


@router.patch("/periods/{period_id}/status", response_model=LeavePeriodResponse)
async def set_period_status(
    period_id: uuid.UUID,
    body: PeriodStatusInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> LeavePeriodResponse:
    return LeavePeriodResponse.model_validate(
        await LeaveService(session).set_period_status(user, period_id, body.status)
    )


@router.post(
    "/entitlements", response_model=EntitlementResponse, status_code=status.HTTP_201_CREATED
)
async def create_entitlement(
    body: EntitlementInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> EntitlementResponse:
    return EntitlementResponse.model_validate(await LeaveService(session).entitlement(user, body))


@router.get("/balances/{entitlement_id}", response_model=BalanceResponse)
async def get_balance(
    entitlement_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.view")],
) -> BalanceResponse:
    return await LeaveService(session).balance(user, entitlement_id)


@router.get("/my/balances", response_model=list[BalanceResponse])
async def my_balances(
    session: Session,
    user: Annotated[User, require_permission("leave.view_own")],
) -> list[BalanceResponse]:
    return await LeaveService(session).my_balances(user)


@router.get("/balances", response_model=BalancePage)
async def list_balances(
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
    employee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    leave_period_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=160),
    sort_by: Literal["employee", "department", "leave_type", "period", "available"] = "employee",
    sort_order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: LeavePageSize = LeavePageSize.TWENTY_FIVE,
) -> BalancePage:
    return await LeaveService(session).list_balances(
        user,
        employee_id=employee_id,
        department_id=department_id,
        leave_type_id=leave_type_id,
        leave_period_id=leave_period_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=int(page_size),
    )


@router.get("/ledger", response_model=LedgerPage)
async def balance_history(
    session: Session,
    user: Annotated[User, require_permission("leave.balances.view")],
    employee_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    leave_period_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: LeavePageSize = LeavePageSize.TWENTY_FIVE,
) -> LedgerPage:
    return await LeaveService(session).balance_history(
        user,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        leave_period_id=leave_period_id,
        page=page,
        page_size=int(page_size),
    )


@router.get("/requests", response_model=LeaveRequestPage)
async def list_requests(
    session: Session,
    user: Annotated[User, require_permission("leave.view_own")],
    scope: Literal["mine", "team", "pending", "recently_reviewed", "organization"] = "mine",
    employee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    request_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(default=None, max_length=160),
    sort_by: Literal["created_at", "start_date", "end_date", "status", "duration"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: LeavePageSize = LeavePageSize.TWENTY_FIVE,
) -> LeaveRequestPage:
    return await LeaveService(session).list_requests(
        user,
        scope=scope,
        employee_id=employee_id,
        department_id=department_id,
        leave_type_id=leave_type_id,
        request_status=request_status,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=int(page_size),
    )


@router.get("/requests/{request_id}", response_model=LeaveRequestDetail)
async def request_detail(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.view_own")],
) -> LeaveRequestDetail:
    return await LeaveService(session).request_detail(user, request_id)


@router.get("/my/summary", response_model=LeaveSummaryResponse)
async def my_summary(
    session: Session,
    user: Annotated[User, require_permission("leave.view_own")],
) -> LeaveSummaryResponse:
    return await LeaveService(session).my_summary(user)


@router.get("/team/summary", response_model=ManagerLeaveSummary)
async def team_summary(
    session: Session,
    user: Annotated[User, require_permission("leave.view_team")],
) -> ManagerLeaveSummary:
    return await LeaveService(session).manager_summary(user)


@router.get("/team/availability", response_model=list[LeaveAvailabilityItem])
async def team_availability(
    start_date: date,
    end_date: date,
    session: Session,
    user: Annotated[User, require_permission("leave.view_team")],
) -> list[LeaveAvailabilityItem]:
    return await LeaveService(session).team_availability(user, start_date, end_date)


@router.get("/reports/usage", response_model=list[LeaveReportRow])
async def usage_report(
    session: Session,
    user: Annotated[User, require_permission("leave.reports.view")],
    group_by: Literal["department", "leave_type"] = "department",
) -> list[LeaveReportRow]:
    return await LeaveService(session).usage_report(user, group_by)


@router.get("/reports/status", response_model=list[LeaveStatusSummary])
async def status_report(
    session: Session,
    user: Annotated[User, require_permission("leave.reports.view")],
    category: Literal["pending", "current", "upcoming", "all"] = "all",
) -> list[LeaveStatusSummary]:
    return await LeaveService(session).status_report(user, category)


@router.get("/reports/balances", response_model=BalancePage)
async def balance_report(
    session: Session,
    user: Annotated[User, require_permission("leave.reports.view")],
    employee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    leave_period_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1),
    page_size: LeavePageSize = LeavePageSize.TWENTY_FIVE,
) -> BalancePage:
    return await LeaveService(session).list_balances(
        user,
        employee_id=employee_id,
        department_id=department_id,
        leave_type_id=leave_type_id,
        leave_period_id=leave_period_id,
        search=search,
        page=page,
        page_size=int(page_size),
    )


@router.get("/exports/requests.csv", response_class=StreamingResponse)
async def export_requests(
    session: Session,
    user: Annotated[User, require_permission("leave.export")],
    employee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    request_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = Query(default=None, max_length=160),
) -> StreamingResponse:
    service = LeaveService(session)
    current_page = 1
    rows: list[LeaveRequestResponse] = []
    while True:
        result = await service.list_requests(
            user,
            scope="organization",
            employee_id=employee_id,
            department_id=department_id,
            leave_type_id=leave_type_id,
            request_status=request_status,
            start_date=start_date,
            end_date=end_date,
            search=search,
            page=current_page,
            page_size=100,
        )
        rows.extend(result.items)
        if len(rows) >= result.total:
            break
        current_page += 1
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "request_id",
            "employee_id",
            "leave_type_id",
            "start_date",
            "end_date",
            "working_days",
            "status",
        ]
    )
    for item in rows:
        writer.writerow(
            [
                item.id,
                item.employee_id,
                item.leave_type_id,
                item.start_date,
                item.end_date,
                item.duration_days,
                item.status,
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leave-requests.csv"},
    )


@router.get("/exports/balances.csv", response_class=StreamingResponse)
async def export_balances(
    session: Session,
    user: Annotated[User, require_permission("leave.export")],
    employee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    leave_period_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=160),
) -> StreamingResponse:
    service = LeaveService(session)
    current_page = 1
    rows: list[BalanceListItem] = []
    while True:
        result = await service.list_balances(
            user,
            employee_id=employee_id,
            department_id=department_id,
            leave_type_id=leave_type_id,
            leave_period_id=leave_period_id,
            search=search,
            page=current_page,
            page_size=100,
        )
        rows.extend(result.items)
        if len(rows) >= result.total:
            break
        current_page += 1
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "employee_number",
            "employee",
            "department",
            "leave_type",
            "period",
            "entitled",
            "used",
            "pending",
            "available",
        ]
    )
    for item in rows:
        writer.writerow(
            [
                item.employee_number,
                item.employee_name,
                item.department_name,
                item.leave_type_name,
                item.period_name,
                item.entitled,
                item.used,
                item.pending,
                item.available,
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leave-balances.csv"},
    )


@router.get("/exports/usage.csv", response_class=StreamingResponse)
async def export_usage(
    session: Session,
    user: Annotated[User, require_permission("leave.export")],
    group_by: Literal["department", "leave_type"] = "department",
) -> StreamingResponse:
    rows = await LeaveService(session).usage_report(user, group_by)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["key", "label", "request_count", "total_days"])
    for item in rows:
        writer.writerow([item.key, item.label, item.request_count, item.total_days])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leave-usage-{group_by}.csv"},
    )


@router.post("/balances/{entitlement_id}/adjustments", response_model=AdjustmentResponse)
async def adjust_balance(
    entitlement_id: uuid.UUID,
    body: AdjustmentInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> AdjustmentResponse:
    return await LeaveService(session).adjust(user, entitlement_id, body)


@router.post("/adjustments", response_model=AdjustmentResponse, status_code=201)
async def create_adjustment(
    body: ControlledAdjustmentInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> AdjustmentResponse:
    return await LeaveService(session).adjust_by_dimensions(user, body)


@router.get("/policy/working-week", response_model=WorkingWeekResponse)
async def get_working_week(
    session: Session,
    user: Annotated[User, require_permission("leave.types.view")],
) -> WorkingWeekResponse:
    return await LeaveService(session).working_week(user)


@router.put("/policy/working-week", response_model=WorkingWeekResponse)
async def set_working_week(
    body: WorkingWeekInput,
    session: Session,
    user: Annotated[User, require_permission("leave.types.manage")],
) -> WorkingWeekResponse:
    return await LeaveService(session).update_working_week(user, body)


@router.post("/working-days", response_model=WorkingDayResult)
async def preview_days(
    body: WorkingDayPreview,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> WorkingDayResult:
    return await LeaveService(session).working_days(
        user, body.start_date, body.end_date, body.half_day
    )


@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: LeaveRequestInput,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).create_request(user, body)
    )


@router.post("/requests/{request_id}/submit", response_model=LeaveRequestResponse)
async def submit_request(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.request")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(await LeaveService(session).submit(user, request_id))


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestResponse)
async def approve_request(
    request_id: uuid.UUID,
    body: ReviewInput,
    session: Session,
    user: Annotated[User, require_permission("leave.approve")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).review(user, request_id, "approved", body.comment)
    )


@router.post("/requests/{request_id}/reject", response_model=LeaveRequestResponse)
async def reject_request(
    request_id: uuid.UUID,
    body: RejectInput,
    session: Session,
    user: Annotated[User, require_permission("leave.reject")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).review(user, request_id, "rejected", body.comment)
    )


@router.post("/requests/{request_id}/withdraw", response_model=LeaveRequestResponse)
async def withdraw_request(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.withdraw_own")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).withdraw(user, request_id)
    )


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
async def cancel_request(
    request_id: uuid.UUID,
    body: ReviewInput,
    session: Session,
    user: Annotated[User, require_permission("leave.withdraw_own")],
) -> LeaveRequestResponse:
    return LeaveRequestResponse.model_validate(
        await LeaveService(session).cancel(user, request_id, body.comment)
    )


@router.post(
    "/requests/{request_id}/attachments", response_model=LeaveAttachmentResponse, status_code=201
)
async def upload_attachment(
    request_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("leave.request")],
    file: LeaveUpload,
) -> LeaveAttachmentResponse:
    service = LeaveService(session)
    await service.ensure_attachment_access(user, request_id)
    content = await file.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValidationError("Leave attachments must be between 1 byte and 25 MB")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValidationError("This file type is not allowed for leave attachments")
    if settings.storage_provider != "local":
        raise RuntimeError("Configured storage provider is unavailable")
    stored = await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).put(
        f"organizations/{user.organization_id}/leave/{request_id}",
        io.BytesIO(content),
        content_type,
        len(content),
    )
    item = await service.add_attachment(
        user,
        request_id,
        filename=file.filename or "supporting-document",
        content_type=stored.content_type,
        size=stored.size,
        storage_key=stored.key,
    )
    return LeaveAttachmentResponse.model_validate(item)


@router.get("/requests/{request_id}/attachments", response_model=list[LeaveAttachmentResponse])
async def list_attachments(
    request_id: uuid.UUID,
    session: Session,
    user: Annotated[User, require_permission("leave.view_own")],
) -> list[LeaveAttachmentResponse]:
    return [
        LeaveAttachmentResponse.model_validate(item)
        for item in await LeaveService(session).list_attachments(user, request_id)
    ]


@router.get(
    "/requests/{request_id}/attachments/{attachment_id}/download", response_class=FileResponse
)
async def download_attachment(
    request_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("leave.view_own")],
) -> FileResponse:
    item = await LeaveService(session).attachment_for_download(user, request_id, attachment_id)
    target = await asyncio.to_thread(
        _attachment_path, settings.local_storage_path, item.storage_key
    )
    if target is None:
        raise NotFoundError("Leave attachment not found")
    return FileResponse(
        target,
        media_type=item.content_type,
        filename=item.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/requests/{request_id}/attachments/{attachment_id}", response_model=OperationResponse
)
async def delete_attachment(
    request_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: Annotated[User, require_permission("leave.request")],
) -> OperationResponse:
    key = await LeaveService(session).delete_attachment(user, request_id, attachment_id)
    await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).delete(key)
    return OperationResponse(message="Leave attachment removed")
