"""Business rules for integrated tasks and daily activity."""

# ruff: noqa: E501

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from meetinghq_api.modules.activity.service import Activity, DatabaseActivityPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.meetings.models import Meeting, MeetingActionItem, MeetingAttendee
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import OrganizationUnit
from meetinghq_api.modules.tasks.models import DailyActivity, Task, TaskComment, TaskHistory
from meetinghq_api.modules.tasks.schemas import (
    DailyActivityCreate,
    DailyActivityResponse,
    DailySummary,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskHistoryResponse,
    TaskPage,
    TaskPriority,
    TaskResponse,
    TaskUpdate,
    WeeklySummary,
)
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.shared.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)

OPEN_STATUSES = {"not_started", "in_progress", "blocked", "awaiting_review"}
CLOSED_STATUSES = {"completed", "cancelled"}


class TaskService:
    """Application service; all reads and mutations are organization-bound."""

    def __init__(self, session: AsyncSession, notifications: NotificationService) -> None:
        self.session = session
        self.notifications = notifications
        self.activity = DatabaseActivityPublisher(session)

    @staticmethod
    def permissions(user: User) -> set[str]:
        return {item.name for role in user.roles for item in role.permissions}

    @classmethod
    def can_manage(cls, user: User) -> bool:
        return "tasks.manage" in cls.permissions(user)

    async def create(self, actor: User, body: TaskCreate) -> Task:
        assignee_id = body.assignee_id or actor.id
        assignee = await self._active_user(actor.organization_id, assignee_id)
        await self._assert_assignment_allowed(actor, assignee)
        if body.department_id:
            await self._department(actor.organization_id, body.department_id)
        if body.meeting_id:
            await self._meeting(actor.organization_id, body.meeting_id)
        if body.meeting_action_item_id:
            action = await self._meeting_action(actor.organization_id, body.meeting_action_item_id)
            if body.meeting_id and body.meeting_id != action.meeting_id:
                raise ValidationError("The action item does not belong to the related meeting")
            body.meeting_id = action.meeting_id
        sequence = (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(Task.sequence), 0)).where(
                        Task.organization_id == actor.organization_id
                    )
                )
                or 0
            )
            + 1
        )
        task = Task(
            organization_id=actor.organization_id,
            sequence=sequence,
            title=body.title.strip(),
            description=body.description,
            priority=body.priority,
            assignee_id=assignee.id,
            created_by_id=actor.id,
            assigned_by_id=actor.id if assignee.id != actor.id else None,
            department_id=body.department_id or assignee.department_id,
            team_id=body.team_id,
            meeting_id=body.meeting_id,
            meeting_action_item_id=body.meeting_action_item_id,
            start_date=body.start_date,
            due_date=body.due_date,
            reminder_at=body.reminder_at,
            follow_up_at=body.follow_up_at,
            tags=self._clean_tags(body.tags),
        )
        self.session.add(task)
        await self.session.flush()
        await self._record(task, actor.id, "created", {"assignee_id": str(assignee.id)})
        await self._activity(task, actor.id, "task.created")
        self._audit(actor, "task.created", task.id, {"assignee_id": str(assignee.id)})
        if assignee.id != actor.id:
            await self._notify_assignment(task, assignee, actor, "assigned")
        return task

    async def from_meeting_action(self, actor: User, action_id: uuid.UUID) -> Task:
        action = await self._meeting_action(actor.organization_id, action_id)
        existing = await self.session.scalar(
            select(Task).where(
                Task.organization_id == actor.organization_id,
                Task.meeting_action_item_id == action.id,
                Task.deleted_at.is_(None),
            )
        )
        if existing:
            return existing
        return await self.create(
            actor,
            TaskCreate(
                title=action.title,
                description=action.description,
                assignee_id=action.assigned_to,
                due_date=action.due_date,
                priority=self._priority(action.priority),
                meeting_id=action.meeting_id,
                meeting_action_item_id=action.id,
            ),
        )

    async def list_tasks(
        self,
        actor: User,
        *,
        scope: str = "mine",
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        due: str | None = None,
        sort: str = "due_date",
        direction: str = "asc",
        page: int = 1,
        page_size: int = 25,
    ) -> TaskPage:
        query = select(Task).where(
            Task.organization_id == actor.organization_id,
            Task.deleted_at.is_(None),
        )
        query = query.where(await self._scope_clause(actor, scope))
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if assignee_id:
            await self._assert_visible_user(actor, assignee_id)
            query = query.where(Task.assignee_id == assignee_id)
        if department_id:
            await self._department(actor.organization_id, department_id)
            query = query.where(Task.department_id == department_id)
        today = datetime.now(UTC).date()
        if due == "today":
            query = query.where(Task.due_date == today)
        elif due == "overdue":
            query = query.where(Task.due_date < today, Task.status.in_(OPEN_STATUSES))
        elif due == "week":
            query = query.where(Task.due_date.between(today, today + timedelta(days=7)))
        count = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        order_column = {
            "due_date": Task.due_date,
            "priority": case(
                {"urgent": 4, "high": 3, "normal": 2, "low": 1}, value=Task.priority, else_=0
            ),
            "status": Task.status,
            "created_at": Task.created_at,
            "assignee": Task.assignee_id,
            "completed_at": Task.completed_at,
        }.get(sort, Task.due_date)
        ordering = order_column.desc() if direction == "desc" else order_column.asc()
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(ordering.nulls_last(), Task.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return TaskPage(
            items=[await self._task_response(item) for item in rows],
            total=count,
            page=page,
            page_size=page_size,
            total_pages=max(1, (count + page_size - 1) // page_size),
        )

    async def detail(self, actor: User, task_id: uuid.UUID) -> TaskDetailResponse:
        task = await self._visible_task(actor, task_id)
        comments = list(
            (
                await self.session.scalars(
                    select(TaskComment)
                    .where(TaskComment.task_id == task.id, TaskComment.deleted_at.is_(None))
                    .order_by(TaskComment.created_at.asc())
                )
            ).all()
        )
        history = list(
            (
                await self.session.scalars(
                    select(TaskHistory)
                    .where(TaskHistory.task_id == task.id)
                    .order_by(TaskHistory.created_at.desc())
                )
            ).all()
        )
        return TaskDetailResponse(
            task=await self._task_response(task),
            comments=[await self._comment_response(row) for row in comments],
            history=[await self._history_response(row) for row in history],
        )

    async def update(self, actor: User, task_id: uuid.UUID, body: TaskUpdate) -> Task:
        task = await self._visible_task(actor, task_id)
        await self._assert_task_editable(actor, task)
        changes: dict[str, object] = {}
        values = body.model_dump(exclude_unset=True)
        requested_status = values.get("status")
        if requested_status == "completed" and task.status != "completed":
            if "tasks.complete" not in self.permissions(actor) and not self.can_manage(actor):
                raise AuthorizationError("You cannot complete this task")
        if (
            requested_status in OPEN_STATUSES
            and task.status in CLOSED_STATUSES
            and "tasks.reopen" not in self.permissions(actor)
            and not self.can_manage(actor)
        ):
            raise AuthorizationError("You cannot reopen this task")
        if "assignee_id" in values and values["assignee_id"] != task.assignee_id:
            assignee = await self._active_user(actor.organization_id, values["assignee_id"])
            await self._assert_assignment_allowed(actor, assignee)
            changes["assignee_id"] = str(assignee.id)
            previous_assignee = task.assignee_id
            task.assignee_id = assignee.id
            task.assigned_by_id = actor.id
            if previous_assignee != assignee.id:
                await self._notify_assignment(task, assignee, actor, "reassigned")
        if "department_id" in values and values["department_id"]:
            await self._department(actor.organization_id, values["department_id"])
        for key, value in values.items():
            if key == "assignee_id":
                continue
            if key == "tags" and value is not None:
                value = self._clean_tags(value)
            if getattr(task, key) != value:
                changes[key] = self._value(value)
                setattr(task, key, value)
        if task.status == "completed":
            task.completed_at = task.completed_at or datetime.now(UTC)
            task.progress = 100
        elif "status" in changes and task.completed_at is not None:
            task.completed_at = None
            if task.progress == 100:
                task.progress = 0
        if not changes:
            return task
        event = "completed" if task.status == "completed" else "updated"
        if "status" in changes and task.status in OPEN_STATUSES and task.completed_at is None:
            event = "reopened" if changes.get("status") == "not_started" else "status_changed"
        await self._record(task, actor.id, event, changes)
        await self._activity(task, actor.id, f"task.{event}")
        self._audit(actor, f"task.{event}", task.id, changes)
        if event == "completed" and task.created_by_id != actor.id:
            creator = await self._active_user(
                actor.organization_id, task.created_by_id, allow_inactive=True
            )
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=creator.id,
                notification_type="task.completed",
                category="tasks",
                priority=task.priority,
                title="Task completed",
                body=f"{task.title} was completed.",
                action_url=f"/tasks/{task.id}",
                metadata={"task_id": str(task.id)},
            )
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def archive(self, actor: User, task_id: uuid.UUID) -> None:
        task = await self._visible_task(actor, task_id)
        if task.created_by_id != actor.id and not self.can_manage(actor):
            raise AuthorizationError("You cannot archive this task")
        task.soft_delete(actor.id)
        await self._record(task, actor.id, "archived", {})
        self._audit(actor, "task.archived", task.id, {})

    async def comment(
        self, actor: User, task_id: uuid.UUID, body: TaskCommentCreate
    ) -> TaskComment:
        task = await self._visible_task(actor, task_id)
        if "tasks.comment" not in self.permissions(actor) and not self.can_manage(actor):
            raise AuthorizationError("You cannot comment on tasks")
        comment = TaskComment(
            organization_id=actor.organization_id,
            task_id=task.id,
            author_id=actor.id,
            body=body.body.strip(),
        )
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        await self._record(task, actor.id, "commented", {"comment_id": str(comment.id)})
        await self._activity(task, actor.id, "task.commented")
        self._audit(actor, "task.commented", task.id, {"comment_id": str(comment.id)})
        return comment

    async def record_activity(self, actor: User, body: DailyActivityCreate) -> DailyActivity:
        if "activity.create_own" not in self.permissions(actor) and not self.can_manage(actor):
            raise AuthorizationError("You cannot record daily activity")
        if body.task_id:
            await self._visible_task(actor, body.task_id)
        if body.meeting_id:
            await self._meeting(actor.organization_id, body.meeting_id)
        row = DailyActivity(
            organization_id=actor.organization_id,
            user_id=actor.id,
            department_id=actor.department_id,
            **body.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        await self.activity.publish(
            Activity(
                organization_id=actor.organization_id,
                actor_id=actor.id,
                event_type="daily_activity.recorded",
                subject_type="daily_activity",
                subject_id=row.id,
                payload={"task_id": str(row.task_id) if row.task_id else None},
            )
        )
        self._audit(
            actor,
            "daily_activity.recorded",
            row.id,
            {"activity_date": row.activity_date.isoformat()},
        )
        return row

    async def activities(
        self, actor: User, *, user_id: uuid.UUID | None, page: int, page_size: int
    ) -> tuple[list[DailyActivity], int]:
        owner = user_id or actor.id
        await self._assert_visible_user(actor, owner, activity=True)
        query = select(DailyActivity).where(
            DailyActivity.organization_id == actor.organization_id,
            DailyActivity.user_id == owner,
            DailyActivity.deleted_at.is_(None),
        )
        count = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        DailyActivity.activity_date.desc(), DailyActivity.created_at.desc()
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, count

    async def daily_summary(
        self, actor: User, summary_date: date, user_id: uuid.UUID | None = None
    ) -> DailySummary:
        owner = user_id or actor.id
        await self._assert_visible_user(actor, owner, activity=True)
        today = datetime.now(UTC).date()
        activities, _ = await self.activities(actor, user_id=owner, page=1, page_size=100)
        selected = [row for row in activities if row.activity_date == summary_date]
        completed = int(
            await self.session.scalar(
                select(func.count()).where(
                    Task.organization_id == actor.organization_id,
                    Task.assignee_id == owner,
                    Task.completed_at.is_not(None),
                    func.date(Task.completed_at) == summary_date,
                )
            )
            or 0
        )
        in_progress = int(
            await self.session.scalar(
                select(func.count()).where(
                    Task.organization_id == actor.organization_id,
                    Task.assignee_id == owner,
                    Task.status == "in_progress",
                    Task.deleted_at.is_(None),
                )
            )
            or 0
        )
        overdue = int(
            await self.session.scalar(
                select(func.count()).where(
                    Task.organization_id == actor.organization_id,
                    Task.assignee_id == owner,
                    Task.status.in_(OPEN_STATUSES),
                    Task.due_date < today,
                    Task.deleted_at.is_(None),
                )
            )
            or 0
        )
        upcoming = int(
            await self.session.scalar(
                select(func.count()).where(
                    Task.organization_id == actor.organization_id,
                    Task.assignee_id == owner,
                    Task.status.in_(OPEN_STATUSES),
                    Task.due_date.between(today, today + timedelta(days=7)),
                    Task.deleted_at.is_(None),
                )
            )
            or 0
        )
        meetings = int(
            await self.session.scalar(
                select(func.count())
                .select_from(MeetingAttendee)
                .join(Meeting, Meeting.id == MeetingAttendee.meeting_id)
                .where(
                    Meeting.organization_id == actor.organization_id,
                    MeetingAttendee.user_id == owner,
                    func.date(Meeting.start_datetime) == summary_date,
                )
            )
            or 0
        )
        return DailySummary(
            date=summary_date,
            completed_tasks=completed,
            in_progress_tasks=in_progress,
            overdue_tasks=overdue,
            activities=[await self._activity_response(row) for row in selected],
            blockers=[row.blockers for row in selected if row.blockers],
            meetings_attended=meetings,
            upcoming_due=upcoming,
        )

    async def weekly_summary(
        self, actor: User, start_date: date, user_id: uuid.UUID | None = None
    ) -> WeeklySummary:
        owner = user_id or actor.id
        await self._assert_visible_user(actor, owner, activity=True)
        end_date = start_date + timedelta(days=6)
        today = datetime.now(UTC).date()
        task_base = [
            Task.organization_id == actor.organization_id,
            Task.assignee_id == owner,
            Task.deleted_at.is_(None),
        ]
        completed = int(
            await self.session.scalar(
                select(func.count()).where(
                    *task_base,
                    Task.completed_at.is_not(None),
                    func.date(Task.completed_at).between(start_date, end_date),
                )
            )
            or 0
        )
        pending = int(
            await self.session.scalar(
                select(func.count()).where(*task_base, Task.status.in_(OPEN_STATUSES))
            )
            or 0
        )
        overdue = int(
            await self.session.scalar(
                select(func.count()).where(
                    *task_base, Task.status.in_(OPEN_STATUSES), Task.due_date < today
                )
            )
            or 0
        )
        activity_rows = list(
            (
                await self.session.scalars(
                    select(DailyActivity).where(
                        DailyActivity.organization_id == actor.organization_id,
                        DailyActivity.user_id == owner,
                        DailyActivity.deleted_at.is_(None),
                        DailyActivity.activity_date.between(start_date, end_date),
                    )
                )
            ).all()
        )
        meetings = int(
            await self.session.scalar(
                select(func.count())
                .select_from(MeetingAttendee)
                .join(Meeting, Meeting.id == MeetingAttendee.meeting_id)
                .where(
                    Meeting.organization_id == actor.organization_id,
                    MeetingAttendee.user_id == owner,
                    func.date(Meeting.start_datetime).between(start_date, end_date),
                )
            )
            or 0
        )
        upcoming = int(
            await self.session.scalar(
                select(func.count()).where(
                    *task_base, Task.due_date.between(today, today + timedelta(days=7))
                )
            )
            or 0
        )
        return WeeklySummary(
            start_date=start_date,
            end_date=end_date,
            completed_tasks=completed,
            pending_tasks=pending,
            overdue_tasks=overdue,
            activity_count=len(activity_rows),
            activity_minutes=sum(row.duration_minutes or 0 for row in activity_rows),
            meetings_attended=meetings,
            upcoming_due=upcoming,
        )

    async def process_due_reminders(self) -> int:
        now = datetime.now(UTC)
        rows = list(
            (
                await self.session.scalars(
                    select(Task).where(
                        Task.deleted_at.is_(None),
                        Task.status.in_(OPEN_STATUSES),
                        or_(
                            and_(
                                Task.reminder_at.is_not(None),
                                Task.reminder_at <= now,
                                Task.reminder_sent_at.is_(None),
                            ),
                            and_(
                                Task.follow_up_at.is_not(None),
                                Task.follow_up_at <= now,
                                Task.follow_up_sent_at.is_(None),
                            ),
                        ),
                    )
                )
            ).all()
        )
        delivered = 0
        for task in rows:
            if task.reminder_at and task.reminder_at <= now and task.reminder_sent_at is None:
                await self._notify_due(task, "reminder")
                task.reminder_sent_at = now
                delivered += 1
            if task.follow_up_at and task.follow_up_at <= now and task.follow_up_sent_at is None:
                await self._notify_due(task, "follow_up")
                task.follow_up_sent_at = now
                delivered += 1
        return delivered

    async def _scope_clause(self, actor: User, scope: str) -> ColumnElement[bool]:
        if scope in {"mine", "assigned"}:
            return Task.assignee_id == actor.id
        if scope == "created":
            return Task.created_by_id == actor.id
        if scope == "department":
            if "tasks.view_department" not in self.permissions(actor) and not self.can_manage(
                actor
            ):
                raise AuthorizationError("You cannot view department work")
            if not actor.department_id and not self.can_manage(actor):
                return Task.assignee_id == actor.id
            return (
                Task.department_id == actor.department_id
                if not self.can_manage(actor)
                else Task.organization_id == actor.organization_id
            )
        if scope == "team":
            if "tasks.view_team" not in self.permissions(actor) and not self.can_manage(actor):
                raise AuthorizationError("You cannot view team work")
            return (
                or_(
                    Task.assignee_id == actor.id,
                    Task.assignee_id.in_(select(User.id).where(User.manager_id == actor.id)),
                )
                if not self.can_manage(actor)
                else Task.organization_id == actor.organization_id
            )
        raise ValidationError("Unknown task scope")

    async def _visible_task(self, actor: User, task_id: uuid.UUID) -> Task:
        task = await self.session.scalar(
            select(Task).where(
                Task.id == task_id,
                Task.organization_id == actor.organization_id,
                Task.deleted_at.is_(None),
            )
        )
        if task is None:
            raise NotFoundError("Task not found")
        if task.assignee_id == actor.id or task.created_by_id == actor.id or self.can_manage(actor):
            return task
        assignee = await self._active_user(
            actor.organization_id, task.assignee_id, allow_inactive=True
        )
        if assignee.manager_id == actor.id and "tasks.view_team" in self.permissions(actor):
            return task
        if (
            assignee.department_id == actor.department_id
            and "tasks.view_department" in self.permissions(actor)
        ):
            return task
        raise NotFoundError("Task not found")

    async def _assert_visible_user(
        self, actor: User, user_id: uuid.UUID, activity: bool = False
    ) -> None:
        if user_id == actor.id or self.can_manage(actor):
            return
        target = await self._active_user(actor.organization_id, user_id, allow_inactive=True)
        prefixes = "activity" if activity else "tasks"
        if target.manager_id == actor.id and f"{prefixes}.view_team" in self.permissions(actor):
            return
        if (
            target.department_id == actor.department_id
            and f"{prefixes}.view_department" in self.permissions(actor)
        ):
            return
        raise AuthorizationError("You cannot view this employee's work")

    async def _assert_assignment_allowed(self, actor: User, assignee: User) -> None:
        if assignee.id == actor.id:
            if "tasks.create_own" not in self.permissions(actor) and not self.can_manage(actor):
                raise AuthorizationError("You cannot create tasks")
            return
        if "tasks.assign" not in self.permissions(actor) and not self.can_manage(actor):
            raise AuthorizationError("You cannot assign tasks")
        if self.can_manage(actor):
            return
        if assignee.manager_id == actor.id:
            return
        if (
            assignee.department_id == actor.department_id
            and "tasks.view_department" in self.permissions(actor)
        ):
            return
        raise AuthorizationError("You may only assign work to authorized reports")

    async def _assert_task_editable(self, actor: User, task: Task) -> None:
        """Keep viewing authority separate from authority to change a task."""
        if self.can_manage(actor):
            return
        permissions = self.permissions(actor)
        if task.assignee_id == actor.id or task.created_by_id == actor.id:
            if "tasks.edit_own" in permissions:
                return
            raise AuthorizationError("You cannot edit this task")
        assignee = await self._active_user(
            actor.organization_id, task.assignee_id, allow_inactive=True
        )
        if "tasks.assign" in permissions and assignee.manager_id == actor.id:
            return
        if (
            "tasks.assign" in permissions
            and "tasks.view_department" in permissions
            and assignee.department_id == actor.department_id
        ):
            return
        raise AuthorizationError("You cannot edit this task")

    async def _active_user(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, allow_inactive: bool = False
    ) -> User:
        user = await self.session.scalar(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.removed_at.is_(None),
            )
        )
        if user is None:
            raise NotFoundError("Employee not found")
        if not allow_inactive and (
            user.status != UserStatus.ACTIVE or user.employment_status == "terminated"
        ):
            raise ValidationError("Tasks cannot be assigned to an inactive employee")
        return user

    async def _department(
        self, organization_id: uuid.UUID, department_id: uuid.UUID
    ) -> OrganizationUnit:
        row = await self.session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.id == department_id,
                OrganizationUnit.organization_id == organization_id,
                OrganizationUnit.deleted_at.is_(None),
            )
        )
        if row is None:
            raise NotFoundError("Department not found")
        return row

    async def _meeting(self, organization_id: uuid.UUID, meeting_id: uuid.UUID) -> Meeting:
        row = await self.session.scalar(
            select(Meeting).where(
                Meeting.id == meeting_id, Meeting.organization_id == organization_id
            )
        )
        if row is None:
            raise NotFoundError("Meeting not found")
        return row

    async def _meeting_action(
        self, organization_id: uuid.UUID, action_id: uuid.UUID
    ) -> MeetingActionItem:
        row = await self.session.scalar(
            select(MeetingActionItem)
            .join(Meeting, Meeting.id == MeetingActionItem.meeting_id)
            .where(MeetingActionItem.id == action_id, Meeting.organization_id == organization_id)
        )
        if row is None:
            raise NotFoundError("Meeting action item not found")
        return row

    async def _record(
        self, task: Task, actor_id: uuid.UUID, event_type: str, payload: dict[str, object]
    ) -> None:
        self.session.add(
            TaskHistory(
                organization_id=task.organization_id,
                task_id=task.id,
                actor_id=actor_id,
                event_type=event_type,
                payload=payload,
            )
        )

    async def _activity(self, task: Task, actor_id: uuid.UUID, event_type: str) -> None:
        await self.activity.publish(
            Activity(
                organization_id=task.organization_id,
                actor_id=actor_id,
                event_type=event_type,
                subject_type="task",
                subject_id=task.id,
                payload={"sequence": task.sequence, "title": task.title},
            )
        )

    def _audit(
        self, actor: User, action: str, resource_id: uuid.UUID, metadata: dict[str, object]
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action=action,
                resource="task",
                resource_id=resource_id,
                audit_metadata=metadata,
            )
        )

    async def _notify_assignment(
        self, task: Task, assignee: User, actor: User, action: str
    ) -> None:
        await self.notifications.create_notification(
            organization_id=task.organization_id,
            user_id=assignee.id,
            notification_type=f"task.{action}",
            category="tasks",
            priority=task.priority,
            title=f"Task {action}",
            body=f"{actor.display_name} {action} you: {task.title}",
            action_url=f"/tasks/{task.id}",
            metadata={"task_id": str(task.id), "assigned_by": str(actor.id)},
        )

    async def _notify_due(self, task: Task, kind: str) -> None:
        await self.notifications.create_notification(
            organization_id=task.organization_id,
            user_id=task.assignee_id,
            notification_type=f"task.{kind}",
            category="tasks",
            priority=task.priority,
            title="Task follow-up due" if kind == "follow_up" else "Task reminder",
            body=f"{task.title} needs your attention.",
            action_url=f"/tasks/{task.id}",
            metadata={"task_id": str(task.id)},
        )

    async def _task_response(self, task: Task) -> TaskResponse:
        assignee = await self._active_user(
            task.organization_id, task.assignee_id, allow_inactive=True
        )
        department = (
            await self._department(task.organization_id, task.department_id)
            if task.department_id
            else None
        )
        meeting = (
            await self._meeting(task.organization_id, task.meeting_id) if task.meeting_id else None
        )
        today = datetime.now(UTC).date()
        overdue = bool(task.due_date and task.due_date < today and task.status in OPEN_STATUSES)
        return TaskResponse.model_validate(
            {
                **{
                    key: getattr(task, key)
                    for key in TaskResponse.model_fields
                    if hasattr(task, key)
                },
                "is_overdue": overdue,
                "overdue_days": (today - task.due_date).days if overdue and task.due_date else 0,
                "assignee_name": assignee.display_name,
                "department_name": department.name if department else None,
                "meeting_title": meeting.title if meeting else None,
            }
        )

    async def _comment_response(self, row: TaskComment) -> TaskCommentResponse:
        author = await self._active_user(row.organization_id, row.author_id, allow_inactive=True)
        return TaskCommentResponse.model_validate(
            {
                **{
                    key: getattr(row, key)
                    for key in TaskCommentResponse.model_fields
                    if hasattr(row, key)
                },
                "author_name": author.display_name,
            }
        )

    async def _history_response(self, row: TaskHistory) -> TaskHistoryResponse:
        actor = (
            await self._active_user(row.organization_id, row.actor_id, allow_inactive=True)
            if row.actor_id
            else None
        )
        return TaskHistoryResponse.model_validate(
            {
                **{
                    key: getattr(row, key)
                    for key in TaskHistoryResponse.model_fields
                    if hasattr(row, key)
                },
                "actor_name": actor.display_name if actor else None,
            }
        )

    async def _activity_response(self, row: DailyActivity) -> DailyActivityResponse:
        user = await self._active_user(row.organization_id, row.user_id, allow_inactive=True)
        return DailyActivityResponse.model_validate(
            {
                **{
                    key: getattr(row, key)
                    for key in DailyActivityResponse.model_fields
                    if hasattr(row, key)
                },
                "user_name": user.display_name,
            }
        )

    @staticmethod
    def _clean_tags(tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))[:20]

    @staticmethod
    def _priority(value: str) -> TaskPriority:
        return (
            cast(TaskPriority, value) if value in {"low", "normal", "high", "urgent"} else "normal"
        )

    @staticmethod
    def _value(value: object) -> object:
        return (
            value.isoformat()
            if isinstance(value, (date, datetime))
            else str(value) if isinstance(value, uuid.UUID) else value
        )
