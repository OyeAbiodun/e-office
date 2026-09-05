"""Tasks and daily activity HTTP boundary."""

# ruff: noqa: E501

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.tasks.schemas import (
    DailyActivityCreate,
    DailyActivityResponse,
    DailySummary,
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
from meetinghq_api.shared.responses import OperationResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
TaskReader = Annotated[User, require_permission("tasks.view_own")]
TaskCreator = Annotated[User, require_permission("tasks.create_own")]


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
    return [await task_service._activity_response(row) for row in rows]


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


@router.delete("/{task_id}", response_model=OperationResponse)
async def archive_task(
    task_id: uuid.UUID, session: Session, settings: AppSettings, user: TaskReader
) -> OperationResponse:
    await service(session, settings).archive(user, task_id)
    return OperationResponse(message="Task archived")
