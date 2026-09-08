"""Leave Management HTTP boundary."""

import asyncio
import io
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.leave.schemas import (
    AdjustmentInput,
    BalanceResponse,
    EntitlementInput,
    EntitlementResponse,
    LeaveAttachmentResponse,
    LeavePeriodInput,
    LeavePeriodResponse,
    LeaveRequestInput,
    LeaveRequestResponse,
    LeaveTypeInput,
    LeaveTypeResponse,
    RejectInput,
    ReviewInput,
    WorkingDayPreview,
    WorkingDayResult,
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


def _attachment_path(storage_root: str, storage_key: str) -> Path | None:
    root = Path(storage_root).resolve()
    target = (root / storage_key).resolve()
    return target if root in target.parents and target.is_file() else None


@router.get("/types", response_model=list[LeaveTypeResponse])
async def list_types(
    session: Session, user: Annotated[User, require_permission("leave.types.view")]
) -> list[LeaveTypeResponse]:
    return [
        LeaveTypeResponse.model_validate(v) for v in await LeaveService(session).list_types(user)
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


@router.post("/balances/{entitlement_id}/adjustments", response_model=BalanceResponse)
async def adjust_balance(
    entitlement_id: uuid.UUID,
    body: AdjustmentInput,
    session: Session,
    user: Annotated[User, require_permission("leave.balances.adjust")],
) -> BalanceResponse:
    return await LeaveService(session).adjust(user, entitlement_id, body)


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
