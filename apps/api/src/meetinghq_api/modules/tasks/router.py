"""Tasks and daily activity HTTP boundary."""

# ruff: noqa: E501

import asyncio
import io
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.tasks.schemas import (
    DailyActivityCreate,
    DailyActivityResponse,
    DailySummary,
    TaskAssigneeResponse,
    TaskAttachmentResponse,
    TaskChecklistItemCreate,
    TaskChecklistItemResponse,
    TaskChecklistItemUpdate,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskPage,
    TaskResponse,
    TaskUpdate,
    WeeklySummary,
)
from meetinghq_api.modules.tasks.service import TaskService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
TaskReader = Annotated[User, require_permission("tasks.view_own")]
TaskCreator = Annotated[User, require_permission("tasks.create_own")]
TaskUpload = Annotated[UploadFile, File()]
ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _task_attachment_path(storage_root: str, storage_key: str) -> Path | None:
    root = Path(storage_root).resolve()
    target = (root / storage_key).resolve()
    if root not in target.parents or not target.is_file():
        return None
    return target


def service(session: Session, settings: AppSettings) -> TaskService:
    return TaskService(session, NotificationService(session, settings))


@router.get("", response_model=TaskPage)
async def list_tasks(
    session: Session,
    settings: AppSettings,
    user: TaskReader,
    scope: Literal["mine", "assigned", "created", "team", "department"] = "mine",
    search: str | None = Query(default=None, max_length=160),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assignee_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    due: Literal["today", "overdue", "week"] | None = None,
    sort: Literal[
        "due_date", "priority", "status", "created_at", "assignee", "completed_at"
    ] = "due_date",
    direction: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> TaskPage:
    return await service(session, settings).list_tasks(
        user,
        scope=scope,
        search=search,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        department_id=department_id,
        due=due,
        sort=sort,
        direction=direction,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate, session: Session, settings: AppSettings, user: TaskCreator
) -> TaskResponse:
    task_service = service(session, settings)
    return await task_service._task_response(await task_service.create(user, body))


@router.post("/from-meeting-action/{action_id}", response_model=TaskResponse, status_code=201)
async def create_task_from_action(
    action_id: uuid.UUID, session: Session, settings: AppSettings, user: TaskCreator
) -> TaskResponse:
    task_service = service(session, settings)
    return await task_service._task_response(
        await task_service.from_meeting_action(user, action_id)
    )


@router.get("/assignees", response_model=list[TaskAssigneeResponse])
async def task_assignees(
    session: Session, settings: AppSettings, user: TaskReader
) -> list[TaskAssigneeResponse]:
    return await service(session, settings).assignable_users(user)


@router.get("/activities", response_model=list[DailyActivityResponse])
async def activities(
    session: Session,
    settings: AppSettings,
    user: TaskReader,
    user_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> list[DailyActivityResponse]:
    task_service = service(session, settings)
    rows, _ = await task_service.activities(user, user_id=user_id, page=page, page_size=page_size)
    return await task_service._activity_responses(rows)


@router.post("/activities", response_model=DailyActivityResponse, status_code=201)
async def record_daily_activity(
    body: DailyActivityCreate, session: Session, settings: AppSettings, user: TaskCreator
) -> DailyActivityResponse:
    task_service = service(session, settings)
    return await task_service._activity_response(await task_service.record_activity(user, body))


@router.get("/summary/daily", response_model=DailySummary)
async def daily_summary(
    summary_date: date,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
    user_id: uuid.UUID | None = None,
) -> DailySummary:
    return await service(session, settings).daily_summary(user, summary_date, user_id)


@router.get("/summary/weekly", response_model=WeeklySummary)
async def weekly_summary(
    start_date: date,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
    user_id: uuid.UUID | None = None,
) -> WeeklySummary:
    return await service(session, settings).weekly_summary(user, start_date, user_id)


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def task_detail(
    task_id: uuid.UUID, session: Session, settings: AppSettings, user: TaskReader
) -> TaskDetailResponse:
    return await service(session, settings).detail(user, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, session: Session, settings: AppSettings, user: TaskReader
) -> TaskResponse:
    task_service = service(session, settings)
    return await task_service._task_response(await task_service.update(user, task_id, body))


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
async def add_comment(
    task_id: uuid.UUID,
    body: TaskCommentCreate,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> TaskCommentResponse:
    task_service = service(session, settings)
    return await task_service._comment_response(await task_service.comment(user, task_id, body))


@router.post(
    "/{task_id}/attachments",
    response_model=TaskAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    task_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
    file: TaskUpload,
) -> TaskAttachmentResponse:
    task_service = service(session, settings)
    await task_service.ensure_attachment_upload_allowed(user, task_id)
    content = await file.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValidationError("Task attachments must be between 1 byte and 25 MB")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValidationError("This file type is not allowed for task attachments")
    if settings.storage_provider != "local":
        raise RuntimeError("Configured storage provider is unavailable")
    stored = await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).put(
        f"organizations/{user.organization_id}/tasks/{task_id}",
        io.BytesIO(content),
        content_type,
        len(content),
    )
    row = await task_service.add_attachment(
        user,
        task_id,
        filename=file.filename or "attachment",
        content_type=stored.content_type,
        size=stored.size,
        storage_key=stored.key,
    )
    return task_service._attachment_response(row)


@router.get("/{task_id}/attachments/{attachment_id}/download", response_class=FileResponse)
async def download_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> FileResponse:
    """Download a task file only after task-level authorization succeeds."""
    row = await service(session, settings).attachment_for_download(user, task_id, attachment_id)
    target = await asyncio.to_thread(
        _task_attachment_path, settings.local_storage_path, row.storage_key
    )
    if target is None:
        raise NotFoundError("Task attachment not found")
    return FileResponse(
        target,
        media_type=row.content_type,
        filename=row.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{task_id}/attachments/{attachment_id}", response_model=OperationResponse)
async def delete_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> OperationResponse:
    task_service = service(session, settings)
    storage_key = await task_service.delete_attachment(user, task_id, attachment_id)
    await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).delete(storage_key)
    return OperationResponse(message="Task attachment removed")


@router.post(
    "/{task_id}/checklist",
    response_model=TaskChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_checklist_item(
    task_id: uuid.UUID,
    body: TaskChecklistItemCreate,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> TaskChecklistItemResponse:
    task_service = service(session, settings)
    return task_service._checklist_response(
        await task_service.add_checklist_item(user, task_id, body)
    )


@router.patch("/{task_id}/checklist/{item_id}", response_model=TaskChecklistItemResponse)
async def update_checklist_item(
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    body: TaskChecklistItemUpdate,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> TaskChecklistItemResponse:
    task_service = service(session, settings)
    return task_service._checklist_response(
        await task_service.update_checklist_item(user, task_id, item_id, body)
    )


@router.delete("/{task_id}/checklist/{item_id}", response_model=OperationResponse)
async def delete_checklist_item(
    task_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: TaskReader,
) -> OperationResponse:
    await service(session, settings).delete_checklist_item(user, task_id, item_id)
    return OperationResponse(message="Checklist item removed")


@router.delete("/{task_id}", response_model=OperationResponse)
async def archive_task(
    task_id: uuid.UUID, session: Session, settings: AppSettings, user: TaskReader
) -> OperationResponse:
    await service(session, settings).archive(user, task_id)
    return OperationResponse(message="Task archived")
