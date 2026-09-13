"""Project Management HTTP boundary."""

import asyncio
import io
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.projects.schemas import (
    AttachmentResponse,
    IssueInput,
    IssueResponse,
    IssueUpdate,
    MemberInput,
    MemberResponse,
    MemberUpdate,
    MilestoneInput,
    MilestoneResponse,
    MilestoneUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectPage,
    ProjectReport,
    ProjectSummary,
    ProjectUpdate,
    ProjectUpdateInput,
    RiskInput,
    RiskResponse,
    RiskUpdate,
    UpdateResponse,
)
from meetinghq_api.modules.projects.service import ProjectService
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.tasks.schemas import TaskCreate, TaskResponse
from meetinghq_api.modules.tasks.service import TaskService
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/projects", tags=["projects"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
ProjectReader = Annotated[User, require_permission("projects.view")]
ProjectCreator = Annotated[User, require_permission("projects.create")]
ProjectUpload = Annotated[UploadFile, File()]

ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def project_service(session: Session, settings: AppSettings) -> ProjectService:
    return ProjectService(session, NotificationService(session, settings))


def task_service(session: Session, settings: AppSettings) -> TaskService:
    return TaskService(session, NotificationService(session, settings))


def attachment_path(storage_root: str, storage_key: str) -> Path | None:
    root = Path(storage_root).resolve()
    target = (root / storage_key).resolve()
    return target if root in target.parents and target.is_file() else None


@router.get("", response_model=ProjectPage)
async def list_projects(
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
    search: str | None = Query(default=None, max_length=160),
    manager_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    health: str | None = None,
    priority: str | None = None,
    target_from: date | None = None,
    target_to: date | None = None,
    archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> ProjectPage:
    return await project_service(session, settings).list_projects(
        user,
        search=search,
        manager_id=manager_id,
        department_id=department_id,
        status=status_filter,
        health=health,
        priority=priority,
        target_from=target_from,
        target_to=target_to,
        archived=archived,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, session: Session, settings: AppSettings, user: ProjectCreator
) -> ProjectSummary:
    return await project_service(session, settings).create(user, body)


@router.get("/{project_id}", response_model=ProjectDetail)
async def project_detail(
    project_id: uuid.UUID, session: Session, settings: AppSettings, user: ProjectReader
) -> ProjectDetail:
    return await project_service(session, settings).detail(user, project_id)


@router.patch("/{project_id}", response_model=ProjectSummary)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> ProjectSummary:
    return await project_service(session, settings).update(user, project_id, body)


@router.post("/{project_id}/archive", response_model=OperationResponse)
async def archive_project(
    project_id: uuid.UUID, session: Session, settings: AppSettings, user: ProjectReader
) -> OperationResponse:
    await project_service(session, settings).archive(user, project_id)
    return OperationResponse(message="Project archived")


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    body: MemberInput,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> MemberResponse:
    return await project_service(session, settings).add_member(user, project_id, body)


@router.patch("/{project_id}/members/{member_id}", response_model=MemberResponse)
async def update_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> MemberResponse:
    return await project_service(session, settings).change_member(user, project_id, member_id, body)


@router.delete("/{project_id}/members/{member_id}", response_model=OperationResponse)
async def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> OperationResponse:
    await project_service(session, settings).remove_member(user, project_id, member_id)
    return OperationResponse(message="Project member removed")


@router.post("/{project_id}/milestones", response_model=MilestoneResponse, status_code=201)
async def add_milestone(
    project_id: uuid.UUID,
    body: MilestoneInput,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> MilestoneResponse:
    return await project_service(session, settings).add_milestone(user, project_id, body)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> MilestoneResponse:
    return await project_service(session, settings).update_milestone(
        user, project_id, milestone_id, body
    )


@router.delete("/{project_id}/milestones/{milestone_id}", response_model=OperationResponse)
async def remove_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> OperationResponse:
    await project_service(session, settings).remove_milestone(user, project_id, milestone_id)
    return OperationResponse(message="Project milestone removed")


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_project_task(
    project_id: uuid.UUID,
    body: TaskCreate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> TaskResponse:
    return await project_service(session, settings).create_task(
        user, project_id, body, task_service(session, settings)
    )


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> list[TaskResponse]:
    return await project_service(session, settings).list_project_tasks(
        user, project_id, task_service(session, settings)
    )


@router.put("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def link_project_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
    milestone_id: uuid.UUID | None = None,
) -> TaskResponse:
    return await project_service(session, settings).link_task(
        user, project_id, task_id, milestone_id, task_service(session, settings)
    )


@router.delete("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def unlink_project_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> TaskResponse:
    return await project_service(session, settings).unlink_task(
        user, project_id, task_id, task_service(session, settings)
    )


@router.post("/{project_id}/updates", response_model=UpdateResponse, status_code=201)
async def add_project_update(
    project_id: uuid.UUID,
    body: ProjectUpdateInput,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> UpdateResponse:
    return await project_service(session, settings).add_update(user, project_id, body)


@router.post("/{project_id}/risks", response_model=RiskResponse, status_code=201)
async def add_risk(
    project_id: uuid.UUID,
    body: RiskInput,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> RiskResponse:
    return await project_service(session, settings).add_risk(user, project_id, body)


@router.post("/{project_id}/issues", response_model=IssueResponse, status_code=201)
async def add_issue(
    project_id: uuid.UUID,
    body: IssueInput,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> IssueResponse:
    return await project_service(session, settings).add_issue(user, project_id, body)


@router.patch("/{project_id}/risks/{risk_id}", response_model=RiskResponse)
async def update_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    body: RiskUpdate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> RiskResponse:
    return await project_service(session, settings).update_risk(user, project_id, risk_id, body)


@router.patch("/{project_id}/issues/{issue_id}", response_model=IssueResponse)
async def update_issue(
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: IssueUpdate,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> IssueResponse:
    return await project_service(session, settings).update_issue(user, project_id, issue_id, body)


@router.get("/{project_id}/report", response_model=ProjectReport)
async def project_report(
    project_id: uuid.UUID,
    start_date: date,
    end_date: date,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> ProjectReport:
    return await project_service(session, settings).report(user, project_id, start_date, end_date)


@router.post("/{project_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    project_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
    file: ProjectUpload,
) -> AttachmentResponse:
    content = await file.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValidationError("Project attachments must be between 1 byte and 25 MB")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise ValidationError("This file type is not allowed for project attachments")
    if settings.storage_provider != "local":
        raise RuntimeError("Configured storage provider is unavailable")
    service = project_service(session, settings)
    await service._file_manageable_project(user, project_id)
    stored = await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).put(
        f"organizations/{user.organization_id}/projects/{project_id}",
        io.BytesIO(content),
        content_type,
        len(content),
    )
    return await service.add_attachment(
        user,
        project_id,
        filename=file.filename or "attachment",
        content_type=stored.content_type,
        size=stored.size,
        storage_key=stored.key,
    )


@router.get("/{project_id}/attachments/{attachment_id}/download", response_class=FileResponse)
async def download_attachment(
    project_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> FileResponse:
    row = await project_service(session, settings).attachment_for_download(
        user, project_id, attachment_id
    )
    target = await asyncio.to_thread(attachment_path, settings.local_storage_path, row.storage_key)
    if target is None:
        raise NotFoundError("Project attachment not found")
    return FileResponse(
        target,
        media_type=row.content_type,
        filename=row.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{project_id}/attachments/{attachment_id}", response_model=OperationResponse)
async def delete_attachment(
    project_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    settings: AppSettings,
    user: ProjectReader,
) -> OperationResponse:
    storage_key = await project_service(session, settings).delete_attachment(
        user, project_id, attachment_id
    )
    await LocalStorageProvider(
        settings.local_storage_path, settings.public_storage_url, settings.jwt_secret
    ).delete(storage_key)
    return OperationResponse(message="Project attachment removed")
