"""Project orchestration over canonical MeetingHQ work domains."""

import math
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.activity.service import Activity, DatabaseActivityPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.meetings.models import Meeting
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import OrganizationUnit
from meetinghq_api.modules.projects.models import (
    Project,
    ProjectAttachment,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectRisk,
    ProjectUpdate,
)
from meetinghq_api.modules.projects.repository import ProjectRepository
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
    ProjectUpdateInput,
    RiskInput,
    RiskResponse,
    RiskUpdate,
    UpdateResponse,
)
from meetinghq_api.modules.projects.schemas import (
    ProjectUpdate as ProjectUpdateInputModel,
)
from meetinghq_api.modules.tasks.models import DailyActivity, Task
from meetinghq_api.modules.tasks.schemas import TaskCreate, TaskResponse
from meetinghq_api.modules.tasks.service import CLOSED_STATUSES, TaskService
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.shared.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

PROJECT_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "cancelled"},
    "planned": {"active", "on_hold", "cancelled"},
    "active": {"on_hold", "completed", "cancelled"},
    "on_hold": {"active", "cancelled"},
    "completed": {"archived", "active"},
    "cancelled": {"archived"},
    "archived": set(),
}


class ProjectService:
    def __init__(self, session: AsyncSession, notifications: NotificationService) -> None:
        self.session = session
        self.notifications = notifications
        self.repository = ProjectRepository(session)
        self.activity = DatabaseActivityPublisher(session)

    @staticmethod
    def permissions(user: User) -> set[str]:
        return {permission.name for role in user.roles for permission in role.permissions}

    async def list_projects(
        self,
        actor: User,
        *,
        search: str | None,
        manager_id: uuid.UUID | None,
        department_id: uuid.UUID | None,
        status: str | None,
        health: str | None,
        priority: str | None,
        target_from: date | None,
        target_to: date | None,
        archived: bool,
        page: int,
        page_size: int,
    ) -> ProjectPage:
        query = self.repository.visible_query(actor, "projects.edit" in self.permissions(actor))
        query = query.where(
            Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None)
        )
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Project.name.ilike(term),
                    Project.project_code.ilike(term),
                    Project.description.ilike(term),
                )
            )
        if manager_id:
            query = query.where(Project.project_manager_id == manager_id)
        if department_id:
            query = query.where(Project.department_id == department_id)
        if status:
            query = query.where(Project.status == status)
        if health:
            query = query.where(Project.health == health)
        if priority:
            query = query.where(Project.priority == priority)
        if target_from:
            query = query.where(Project.target_end_date >= target_from)
        if target_to:
            query = query.where(Project.target_end_date <= target_to)
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(Project.updated_at.desc(), Project.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return ProjectPage(
            items=await self._summaries(rows),
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, math.ceil(total / page_size)),
        )

    async def create(self, actor: User, body: ProjectCreate) -> ProjectSummary:
        await self._active_user(actor.organization_id, body.project_manager_id)
        if body.sponsor_id:
            await self._active_user(actor.organization_id, body.sponsor_id)
        await self._organization_references(actor, body.department_id, body.team_id)
        sequence = await self.repository.next_sequence(actor.organization_id)
        code = (body.project_code or f"PRJ-{datetime.now(UTC).year}-{sequence:04d}").upper()
        if await self.session.scalar(
            select(Project.id).where(
                Project.organization_id == actor.organization_id, Project.project_code == code
            )
        ):
            raise ConflictError("Project code already exists")
        project = Project(
            organization_id=actor.organization_id,
            sequence=sequence,
            project_code=code,
            name=body.name.strip(),
            description=body.description,
            project_manager_id=body.project_manager_id,
            sponsor_id=body.sponsor_id,
            department_id=body.department_id,
            team_id=body.team_id,
            start_date=body.start_date,
            target_end_date=body.target_end_date,
            priority=body.priority,
            visibility=body.visibility,
            created_by_id=actor.id,
        )
        self.session.add(project)
        await self.session.flush()
        manager = MemberInput(user_id=body.project_manager_id, role="project_manager")
        await self._add_member(actor, project, manager, notify=True)
        for user_id in dict.fromkeys(body.member_ids):
            if user_id != body.project_manager_id:
                await self._add_member(actor, project, MemberInput(user_id=user_id), notify=True)
        await self._event(actor, project, "project.created", {"project_code": code})
        return (await self._summaries([project]))[0]

    async def detail(self, actor: User, project_id: uuid.UUID) -> ProjectDetail:
        project = await self._visible_project(actor, project_id)
        members = list(
            (
                await self.session.scalars(
                    select(ProjectMember)
                    .where(ProjectMember.project_id == project.id)
                    .order_by(ProjectMember.created_at)
                )
            ).all()
        )
        milestones = list(
            (
                await self.session.scalars(
                    select(ProjectMilestone)
                    .where(ProjectMilestone.project_id == project.id)
                    .order_by(ProjectMilestone.sequence, ProjectMilestone.target_date)
                )
            ).all()
        )
        updates = list(
            (
                await self.session.scalars(
                    select(ProjectUpdate)
                    .where(ProjectUpdate.project_id == project.id)
                    .order_by(ProjectUpdate.reporting_date.desc(), ProjectUpdate.created_at.desc())
                    .limit(100)
                )
            ).all()
        )
        risks = list(
            (
                await self.session.scalars(
                    select(ProjectRisk)
                    .where(ProjectRisk.project_id == project.id)
                    .order_by(ProjectRisk.created_at.desc())
                )
            ).all()
        )
        issues = list(
            (
                await self.session.scalars(
                    select(ProjectIssue)
                    .where(ProjectIssue.project_id == project.id)
                    .order_by(ProjectIssue.created_at.desc())
                )
            ).all()
        )
        attachments = list(
            (
                await self.session.scalars(
                    select(ProjectAttachment)
                    .where(
                        ProjectAttachment.project_id == project.id,
                        ProjectAttachment.deleted_at.is_(None),
                    )
                    .order_by(ProjectAttachment.created_at.desc())
                )
            ).all()
        )
        meetings = list(
            (
                await self.session.scalars(
                    select(Meeting)
                    .where(
                        Meeting.organization_id == actor.organization_id,
                        Meeting.project_id == project.id,
                    )
                    .order_by(Meeting.start_datetime.desc())
                    .limit(100)
                )
            ).all()
        )
        activity = list(
            (
                await self.session.scalars(
                    select(ActivityEvent)
                    .where(
                        ActivityEvent.organization_id == actor.organization_id,
                        ActivityEvent.subject_type == "project",
                        ActivityEvent.subject_id == project.id,
                    )
                    .order_by(ActivityEvent.occurred_at.desc())
                    .limit(100)
                )
            ).all()
        )
        users = await self._users(
            actor.organization_id,
            {row.user_id for row in members}
            | {row.owner_id for row in milestones + risks + issues if row.owner_id}
            | {row.created_by_id for row in updates},
        )
        return ProjectDetail(
            project=(await self._summaries([project]))[0],
            members=[
                MemberResponse.model_validate(
                    {
                        **self._model(row, MemberResponse),
                        "display_name": users[row.user_id].display_name,
                        "job_title": users[row.user_id].job_title,
                        "avatar_url": users[row.user_id].avatar_url,
                    }
                )
                for row in members
            ],
            milestones=[
                MilestoneResponse.model_validate(
                    {
                        **self._model(row, MilestoneResponse),
                        "owner_name": (
                            users[row.owner_id].display_name if row.owner_id in users else None
                        ),
                    }
                )
                for row in milestones
            ],
            updates=[
                UpdateResponse.model_validate(
                    {
                        **self._model(row, UpdateResponse),
                        "author_name": (
                            users[row.created_by_id].display_name
                            if row.created_by_id in users
                            else None
                        ),
                    }
                )
                for row in updates
            ],
            risks=[
                RiskResponse.model_validate(
                    {
                        **self._model(row, RiskResponse),
                        "owner_name": (
                            users[row.owner_id].display_name if row.owner_id in users else None
                        ),
                    }
                )
                for row in risks
            ],
            issues=[
                IssueResponse.model_validate(
                    {
                        **self._model(row, IssueResponse),
                        "owner_name": (
                            users[row.owner_id].display_name if row.owner_id in users else None
                        ),
                    }
                )
                for row in issues
            ],
            attachments=[AttachmentResponse.model_validate(row) for row in attachments],
            meetings=[self._meeting_dict(row) for row in meetings],
            activity=[
                {
                    "id": str(row.id),
                    "event_type": row.event_type,
                    "actor_id": str(row.actor_id) if row.actor_id else None,
                    "payload": row.payload,
                    "created_at": row.occurred_at.isoformat(),
                }
                for row in activity
            ],
        )

    async def update(
        self, actor: User, project_id: uuid.UUID, body: ProjectUpdateInputModel
    ) -> ProjectSummary:
        project = await self._manageable_project(actor, project_id)
        values = body.model_dump(exclude_unset=True, exclude={"completion_override"})
        previous_manager_id = project.project_manager_id
        if "project_manager_id" in values:
            manager_id = cast(uuid.UUID, values["project_manager_id"])
            if (
                "projects.edit" not in self.permissions(actor)
                and project.project_manager_id != actor.id
            ):
                raise AuthorizationError("You cannot transfer project management")
            await self._active_user(actor.organization_id, manager_id)
            if manager_id != previous_manager_id:
                await self._transfer_manager(actor, project, manager_id)
        if "department_id" in values or "team_id" in values:
            await self._organization_references(
                actor,
                cast(uuid.UUID | None, values.get("department_id", project.department_id)),
                cast(uuid.UUID | None, values.get("team_id", project.team_id)),
            )
        target = values.get("status")
        if target and target != project.status:
            if (
                target == "archived"
                and "projects.archive" not in self.permissions(actor)
                and project.project_manager_id != actor.id
            ):
                raise AuthorizationError("You cannot archive this project")
            if cast(str, target) not in PROJECT_TRANSITIONS.get(project.status, set()):
                raise ValidationError(
                    f"Cannot transition project from {project.status} to {target}"
                )
            if target == "completed":
                warnings = await self._completion_warnings(project)
                if warnings and not body.completion_override:
                    raise ConflictError("Completion requires confirmation: " + "; ".join(warnings))
                values["actual_end_date"] = datetime.now(UTC).date()
                values["health"] = "completed"
            if target == "archived":
                values["archived_at"] = datetime.now(UTC)
        changes: dict[str, object] = {}
        for key, value in values.items():
            if getattr(project, key) != value:
                changes[key] = self._value(value)
                setattr(project, key, value)
        if changes:
            await self._event(actor, project, "project.updated", changes)
            if project.project_manager_id != previous_manager_id:
                await self._event(
                    actor,
                    project,
                    "project.manager_transferred",
                    {
                        "previous_manager_id": str(previous_manager_id),
                        "project_manager_id": str(project.project_manager_id),
                    },
                )
        await self.session.flush()
        return (await self._summaries([project]))[0]

    async def archive(self, actor: User, project_id: uuid.UUID) -> None:
        project = await self._visible_project(actor, project_id)
        if (
            "projects.archive" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot archive this project")
        if project.status not in {"completed", "cancelled"}:
            raise ValidationError("Only completed or cancelled projects can be archived")
        project.status = "archived"
        project.archived_at = datetime.now(UTC)
        await self._event(actor, project, "project.archived", {})

    async def add_member(
        self, actor: User, project_id: uuid.UUID, body: MemberInput
    ) -> MemberResponse:
        project = await self._member_manageable_project(actor, project_id)
        row = await self._add_member(actor, project, body, notify=True)
        user = await self._active_user(actor.organization_id, row.user_id)
        return MemberResponse.model_validate(
            {
                **self._model(row, MemberResponse),
                "display_name": user.display_name,
                "job_title": user.job_title,
                "avatar_url": user.avatar_url,
            }
        )

    async def change_member(
        self, actor: User, project_id: uuid.UUID, member_id: uuid.UUID, body: MemberUpdate
    ) -> MemberResponse:
        project = await self._member_manageable_project(actor, project_id)
        row = await self._member(project, member_id)
        if row.user_id == project.project_manager_id and body.role != "project_manager":
            raise ConflictError("Transfer project management before changing this role")
        row.role = body.role
        await self._event(
            actor,
            project,
            "project.member_changed",
            {"user_id": str(row.user_id), "role": row.role},
        )
        user = await self._active_user(actor.organization_id, row.user_id, allow_inactive=True)
        return MemberResponse.model_validate(
            {
                **self._model(row, MemberResponse),
                "display_name": user.display_name,
                "job_title": user.job_title,
                "avatar_url": user.avatar_url,
            }
        )

    async def remove_member(self, actor: User, project_id: uuid.UUID, member_id: uuid.UUID) -> None:
        project = await self._member_manageable_project(actor, project_id)
        row = await self._member(project, member_id)
        if row.user_id == project.project_manager_id:
            raise ConflictError("The project manager cannot be removed")
        await self.session.delete(row)
        await self._event(actor, project, "project.member_removed", {"user_id": str(row.user_id)})

    async def add_milestone(
        self, actor: User, project_id: uuid.UUID, body: MilestoneInput
    ) -> MilestoneResponse:
        project = await self._milestone_manageable_project(actor, project_id)
        if body.owner_id:
            await self._project_user(project, body.owner_id)
        sequence = (
            body.sequence
            if body.sequence is not None
            else int(
                await self.session.scalar(
                    select(func.coalesce(func.max(ProjectMilestone.sequence), -1)).where(
                        ProjectMilestone.project_id == project.id
                    )
                )
                or -1
            )
            + 1
        )
        row = ProjectMilestone(
            organization_id=actor.organization_id,
            project_id=project.id,
            sequence=sequence,
            **body.model_dump(exclude={"sequence"}),
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(
            actor, project, "project.milestone_created", {"milestone_id": str(row.id)}
        )
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return MilestoneResponse.model_validate(
            {
                **self._model(row, MilestoneResponse),
                "owner_name": owner.display_name if owner else None,
            }
        )

    async def update_milestone(
        self, actor: User, project_id: uuid.UUID, milestone_id: uuid.UUID, body: MilestoneUpdate
    ) -> MilestoneResponse:
        project = await self._milestone_manageable_project(actor, project_id)
        row = await self._milestone(project, milestone_id)
        values = body.model_dump(exclude_unset=True)
        if values.get("owner_id"):
            await self._project_user(project, cast(uuid.UUID, values["owner_id"]))
        for key, value in values.items():
            setattr(row, key, value)
        if row.status == "completed":
            row.completion_date = row.completion_date or datetime.now(UTC).date()
            row.progress = 100
        elif "status" in values and row.completion_date:
            row.completion_date = None
        await self._event(
            actor,
            project,
            "project.milestone_updated",
            {
                "milestone_id": str(row.id),
                **{key: self._value(value) for key, value in values.items()},
            },
        )
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return MilestoneResponse.model_validate(
            {
                **self._model(row, MilestoneResponse),
                "owner_name": owner.display_name if owner else None,
            }
        )

    async def create_task(
        self, actor: User, project_id: uuid.UUID, body: TaskCreate, tasks: TaskService
    ) -> TaskResponse:
        project = await self._manageable_project(actor, project_id)
        if not self.permissions(actor).intersection({"tasks.create_own", "tasks.manage"}):
            raise AuthorizationError("You cannot create tasks")
        body.project_id = project.id
        if body.milestone_id:
            await self._milestone(project, body.milestone_id)
        task = await tasks.create(actor, body)
        await self._event(actor, project, "project.task_created", {"task_id": str(task.id)})
        return await tasks._task_response(task)

    async def list_project_tasks(
        self,
        actor: User,
        project_id: uuid.UUID,
        tasks: TaskService,
    ) -> list[TaskResponse]:
        project = await self._visible_project(actor, project_id)
        rows = list(
            (
                await self.session.scalars(
                    select(Task)
                    .where(
                        Task.organization_id == actor.organization_id,
                        Task.project_id == project.id,
                        Task.deleted_at.is_(None),
                    )
                    .order_by(Task.due_date, Task.priority.desc(), Task.id)
                    .limit(500)
                )
            ).all()
        )
        return await tasks._task_responses(rows)

    async def link_task(
        self,
        actor: User,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        milestone_id: uuid.UUID | None,
        tasks: TaskService,
    ) -> TaskResponse:
        project = await self._manageable_project(actor, project_id)
        task = await tasks._visible_task(actor, task_id)
        if task.project_id and task.project_id != project.id:
            raise ConflictError("Task is already linked to another project")
        if milestone_id:
            await self._milestone(project, milestone_id)
        if task.project_id == project.id and task.milestone_id == milestone_id:
            return await tasks._task_response(task)
        task.project_id = project.id
        task.milestone_id = milestone_id
        await tasks._record(
            task,
            actor.id,
            "project_linked",
            {
                "project_id": str(project.id),
                "milestone_id": str(milestone_id) if milestone_id else None,
            },
        )
        await self._event(actor, project, "project.task_linked", {"task_id": str(task.id)})
        # Materialize the updated task after the transaction's pending audit/activity
        # rows have been flushed.  This prevents response serialization from trying
        # to lazy-refresh an expired ORM instance outside SQLAlchemy's async greenlet.
        await self.session.flush()
        await self.session.refresh(task)
        return await tasks._task_response(task)

    async def unlink_task(
        self,
        actor: User,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        tasks: TaskService,
    ) -> TaskResponse:
        project = await self._manageable_project(actor, project_id)
        task = await tasks._visible_task(actor, task_id)
        if task.project_id != project.id:
            raise NotFoundError("Project task not found")
        task.project_id = None
        task.milestone_id = None
        await tasks._record(task, actor.id, "project_unlinked", {"project_id": str(project.id)})
        await self._event(actor, project, "project.task_unlinked", {"task_id": str(task.id)})
        await self.session.flush()
        await self.session.refresh(task)
        return await tasks._task_response(task)

    async def remove_milestone(
        self, actor: User, project_id: uuid.UUID, milestone_id: uuid.UUID
    ) -> None:
        project = await self._milestone_manageable_project(actor, project_id)
        row = await self._milestone(project, milestone_id)
        if await self.session.scalar(select(Task.id).where(Task.milestone_id == row.id).limit(1)):
            raise ConflictError("Move or unlink milestone tasks before removing the milestone")
        await self.session.delete(row)
        await self._event(
            actor, project, "project.milestone_removed", {"milestone_id": str(row.id)}
        )

    async def add_update(
        self, actor: User, project_id: uuid.UUID, body: ProjectUpdateInput
    ) -> UpdateResponse:
        project = await self._manageable_project(actor, project_id)
        row = ProjectUpdate(
            organization_id=actor.organization_id,
            project_id=project.id,
            created_by_id=actor.id,
            **body.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(actor, project, "project.update_recorded", {"update_id": str(row.id)})
        return UpdateResponse.model_validate(
            {**self._model(row, UpdateResponse), "author_name": actor.display_name}
        )

    async def add_risk(self, actor: User, project_id: uuid.UUID, body: RiskInput) -> RiskResponse:
        project = await self._risk_manageable_project(actor, project_id)
        if body.owner_id:
            await self._project_user(project, body.owner_id)
        row = ProjectRisk(
            organization_id=actor.organization_id,
            project_id=project.id,
            created_by_id=actor.id,
            **body.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(actor, project, "project.risk_created", {"risk_id": str(row.id)})
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return RiskResponse.model_validate(
            {**self._model(row, RiskResponse), "owner_name": owner.display_name if owner else None}
        )

    async def add_issue(
        self, actor: User, project_id: uuid.UUID, body: IssueInput
    ) -> IssueResponse:
        project = await self._issue_manageable_project(actor, project_id)
        if body.owner_id:
            await self._project_user(project, body.owner_id)
        row = ProjectIssue(
            organization_id=actor.organization_id,
            project_id=project.id,
            created_by_id=actor.id,
            **body.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(actor, project, "project.issue_created", {"issue_id": str(row.id)})
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return IssueResponse.model_validate(
            {**self._model(row, IssueResponse), "owner_name": owner.display_name if owner else None}
        )

    async def update_risk(
        self,
        actor: User,
        project_id: uuid.UUID,
        risk_id: uuid.UUID,
        body: RiskUpdate,
    ) -> RiskResponse:
        project = await self._risk_manageable_project(actor, project_id)
        row = await self.session.scalar(
            select(ProjectRisk).where(
                ProjectRisk.id == risk_id,
                ProjectRisk.project_id == project.id,
                ProjectRisk.organization_id == actor.organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Project risk not found")
        values = body.model_dump(exclude_unset=True)
        if values.get("owner_id"):
            await self._project_user(project, cast(uuid.UUID, values["owner_id"]))
        for key, value in values.items():
            setattr(row, key, value)
        await self._event(
            actor,
            project,
            "project.risk_updated",
            {"risk_id": str(row.id), **{key: self._value(value) for key, value in values.items()}},
        )
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return RiskResponse.model_validate(
            {**self._model(row, RiskResponse), "owner_name": owner.display_name if owner else None}
        )

    async def update_issue(
        self,
        actor: User,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        body: IssueUpdate,
    ) -> IssueResponse:
        project = await self._issue_manageable_project(actor, project_id)
        row = await self.session.scalar(
            select(ProjectIssue).where(
                ProjectIssue.id == issue_id,
                ProjectIssue.project_id == project.id,
                ProjectIssue.organization_id == actor.organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Project issue not found")
        values = body.model_dump(exclude_unset=True)
        if values.get("owner_id"):
            await self._project_user(project, cast(uuid.UUID, values["owner_id"]))
        if values.get("status") in {"resolved", "closed"} and not values.get(
            "resolution", row.resolution
        ):
            raise ValidationError("A resolution is required before resolving an issue")
        for key, value in values.items():
            setattr(row, key, value)
        await self._event(
            actor,
            project,
            "project.issue_updated",
            {"issue_id": str(row.id), **{key: self._value(value) for key, value in values.items()}},
        )
        owner = (
            await self._active_user(actor.organization_id, row.owner_id, allow_inactive=True)
            if row.owner_id
            else None
        )
        return IssueResponse.model_validate(
            {**self._model(row, IssueResponse), "owner_name": owner.display_name if owner else None}
        )

    async def report(
        self, actor: User, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> ProjectReport:
        if end_date < start_date:
            raise ValidationError("end_date cannot precede start_date")
        project = await self._visible_project(actor, project_id)
        if (
            "projects.generate_reports" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot generate project reports")
        detail = await self.detail(actor, project.id)
        tasks = list(
            (
                await self.session.scalars(
                    select(Task).where(
                        Task.organization_id == actor.organization_id,
                        Task.project_id == project.id,
                        Task.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        period_tasks = [task for task in tasks if start_date <= task.created_at.date() <= end_date]
        activities = list(
            (
                await self.session.scalars(
                    select(DailyActivity)
                    .where(
                        DailyActivity.organization_id == actor.organization_id,
                        DailyActivity.project_id == project.id,
                        DailyActivity.activity_date.between(start_date, end_date),
                        DailyActivity.deleted_at.is_(None),
                    )
                    .order_by(DailyActivity.activity_date)
                )
            ).all()
        )
        meetings = list(
            (
                await self.session.scalars(
                    select(Meeting)
                    .where(
                        Meeting.organization_id == actor.organization_id,
                        Meeting.project_id == project.id,
                        func.date(Meeting.start_datetime).between(start_date, end_date),
                    )
                    .order_by(Meeting.start_datetime)
                )
            ).all()
        )
        updates = [item for item in detail.updates if start_date <= item.reporting_date <= end_date]
        today = datetime.now(UTC).date()
        completed = len([task for task in period_tasks if task.status == "completed"])
        overdue = len(
            [
                task
                for task in tasks
                if task.due_date and task.due_date < today and task.status not in CLOSED_STATUSES
            ]
        )
        narrative = (
            updates[0].summary
            if updates
            else (
                f"{detail.project.name} is {detail.project.status.replace('_', ' ')} "
                f"with {detail.project.progress}% progress."
            )
        )
        await self._event(
            actor,
            project,
            "project.report_generated",
            {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
        upcoming_deadlines: list[dict[str, object]] = [
            cast(
                dict[str, object],
                {
                    "type": "task",
                    "id": str(task.id),
                    "title": task.title,
                    "date": task.due_date.isoformat(),
                },
            )
            for task in tasks
            if task.due_date and task.due_date >= today
        ][:20]
        return ProjectReport(
            project=detail.project,
            start_date=start_date,
            end_date=end_date,
            executive_summary=narrative,
            milestones=detail.milestones,
            tasks_total=len(period_tasks),
            tasks_completed=completed,
            tasks_overdue=overdue,
            activities=[
                {
                    "id": str(row.id),
                    "date": row.activity_date.isoformat(),
                    "summary": row.summary,
                    "user_id": str(row.user_id),
                }
                for row in activities
            ],
            updates=updates,
            risks=[row for row in detail.risks if row.status != "closed"],
            issues=[row for row in detail.issues if row.status not in {"resolved", "closed"}],
            meetings=[self._meeting_dict(row) for row in meetings],
            upcoming_deadlines=upcoming_deadlines,
            generated_at=datetime.now(UTC),
        )

    async def add_attachment(
        self,
        actor: User,
        project_id: uuid.UUID,
        *,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
    ) -> AttachmentResponse:
        project = await self._file_manageable_project(actor, project_id)
        safe_name = Path(filename).name.strip()
        if not safe_name or safe_name in {".", ".."}:
            raise ValidationError("Attachment filename is invalid")
        row = ProjectAttachment(
            organization_id=actor.organization_id,
            project_id=project.id,
            filename=safe_name[:255],
            content_type=content_type,
            size=size,
            storage_key=storage_key,
            uploaded_by_id=actor.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(
            actor, project, "project.attachment_added", {"attachment_id": str(row.id)}
        )
        return AttachmentResponse.model_validate(row)

    async def attachment_for_download(
        self, actor: User, project_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> ProjectAttachment:
        project = await self._visible_project(actor, project_id)
        row = await self.session.scalar(
            select(ProjectAttachment).where(
                ProjectAttachment.id == attachment_id,
                ProjectAttachment.project_id == project.id,
                ProjectAttachment.organization_id == actor.organization_id,
                ProjectAttachment.deleted_at.is_(None),
            )
        )
        if row is None:
            raise NotFoundError("Project attachment not found")
        return row

    async def delete_attachment(
        self, actor: User, project_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> str:
        project = await self._file_manageable_project(actor, project_id)
        row = await self.attachment_for_download(actor, project.id, attachment_id)
        row.soft_delete(actor.id)
        await self._event(
            actor, project, "project.attachment_removed", {"attachment_id": str(row.id)}
        )
        return row.storage_key

    async def _visible_project(self, actor: User, project_id: uuid.UUID) -> Project:
        query = self.repository.visible_query(
            actor, "projects.edit" in self.permissions(actor)
        ).where(Project.id == project_id)
        project = await self.session.scalar(query)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    async def _manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._visible_project(actor, project_id)
        if "projects.edit" in self.permissions(actor) or project.project_manager_id == actor.id:
            if project.status == "archived":
                raise ConflictError("Archived projects are read-only")
            return project
        member_role = await self.session.scalar(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == actor.id,
                ProjectMember.organization_id == actor.organization_id,
            )
        )
        if member_role == "project_lead":
            return project
        raise AuthorizationError("You cannot manage this project")

    async def _member_manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._visible_project(actor, project_id)
        if (
            "projects.manage_members" in self.permissions(actor)
            or project.project_manager_id == actor.id
        ):
            return project
        raise AuthorizationError("You cannot manage project members")

    async def _milestone_manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._manageable_project(actor, project_id)
        if (
            "projects.manage_milestones" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot manage project milestones")
        return project

    async def _risk_manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._manageable_project(actor, project_id)
        if (
            "projects.manage_risks" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot manage project risks")
        return project

    async def _issue_manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._manageable_project(actor, project_id)
        if (
            "projects.manage_issues" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot manage project issues")
        return project

    async def _file_manageable_project(self, actor: User, project_id: uuid.UUID) -> Project:
        project = await self._manageable_project(actor, project_id)
        if (
            "projects.manage_files" not in self.permissions(actor)
            and project.project_manager_id != actor.id
        ):
            raise AuthorizationError("You cannot manage project files")
        return project

    async def _transfer_manager(self, actor: User, project: Project, manager_id: uuid.UUID) -> None:
        current_manager_id = project.project_manager_id
        new_membership = await self.session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == manager_id,
                ProjectMember.organization_id == actor.organization_id,
            )
        )
        if new_membership is None:
            await self._add_member(
                actor,
                project,
                MemberInput(user_id=manager_id, role="project_manager"),
                notify=True,
            )
        else:
            new_membership.role = "project_manager"
        old_membership = await self.session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == current_manager_id,
                ProjectMember.organization_id == actor.organization_id,
            )
        )
        if old_membership is not None:
            old_membership.role = "project_lead"

    async def _add_member(
        self, actor: User, project: Project, body: MemberInput, *, notify: bool
    ) -> ProjectMember:
        user = await self._active_user(actor.organization_id, body.user_id)
        if await self.session.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
            )
        ):
            raise ConflictError("Employee is already a project member")
        row = ProjectMember(
            organization_id=actor.organization_id,
            project_id=project.id,
            user_id=user.id,
            role=body.role,
            added_by_id=actor.id,
        )
        self.session.add(row)
        await self.session.flush()
        await self._event(
            actor, project, "project.member_added", {"user_id": str(user.id), "role": body.role}
        )
        if notify and user.id != actor.id:
            await self.notifications.create_notification(
                organization_id=actor.organization_id,
                user_id=user.id,
                notification_type="project.member_added",
                category="projects",
                priority="normal",
                title="Added to project",
                body=f"You were added to {project.name}.",
                action_url=f"/projects/{project.id}",
                metadata={"project_id": str(project.id)},
            )
        return row

    async def _summaries(self, projects: list[Project]) -> list[ProjectSummary]:
        if not projects:
            return []
        project_ids = [row.id for row in projects]
        users = await self._users(
            projects[0].organization_id, {row.project_manager_id for row in projects}
        )
        department_ids = {row.department_id for row in projects if row.department_id}
        departments = (
            {
                row.id: row
                for row in list(
                    (
                        await self.session.scalars(
                            select(OrganizationUnit).where(
                                OrganizationUnit.organization_id == projects[0].organization_id,
                                OrganizationUnit.id.in_(department_ids),
                            )
                        )
                    ).all()
                )
            }
            if department_ids
            else {}
        )
        members = await self._counts(ProjectMember.project_id, project_ids)
        milestones = await self._counts(ProjectMilestone.project_id, project_ids)
        milestone_progress = await self._milestone_progress(project_ids)
        tasks = await self._task_counts(project_ids)
        risks = await self._status_counts(ProjectRisk, project_ids, {"open", "monitoring"})
        issues = await self._status_counts(ProjectIssue, project_ids, {"open", "in_progress"})
        result: list[ProjectSummary] = []
        for project in projects:
            task_stats = tasks.get(project.id, (0, 0, 0))
            progress = project.manual_progress or 0
            if project.progress_mode == "task_based" and task_stats[0]:
                progress = round(task_stats[1] * 100 / task_stats[0])
            elif project.progress_mode == "milestone_based":
                progress = milestone_progress.get(project.id, 0)
            result.append(
                ProjectSummary.model_validate(
                    {
                        **self._model(project, ProjectSummary),
                        "progress": progress,
                        "manager_name": (
                            users[project.project_manager_id].display_name
                            if project.project_manager_id in users
                            else None
                        ),
                        "department_name": (
                            departments[project.department_id].name
                            if project.department_id in departments
                            else None
                        ),
                        "member_count": members.get(project.id, 0),
                        "task_count": task_stats[0],
                        "completed_task_count": task_stats[1],
                        "overdue_task_count": task_stats[2],
                        "milestone_count": milestones.get(project.id, 0),
                        "open_risk_count": risks.get(project.id, 0),
                        "open_issue_count": issues.get(project.id, 0),
                    }
                )
            )
        return result

    async def _task_counts(
        self, project_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int, int]]:
        today = datetime.now(UTC).date()
        rows = (
            await self.session.execute(
                select(
                    Task.project_id,
                    func.count(Task.id).filter(Task.status != "cancelled"),
                    func.count(Task.id).filter(Task.status == "completed"),
                    func.count(Task.id).filter(
                        Task.due_date < today, Task.status.not_in(CLOSED_STATUSES)
                    ),
                )
                .where(Task.project_id.in_(project_ids), Task.deleted_at.is_(None))
                .group_by(Task.project_id)
            )
        ).all()
        return {
            cast(uuid.UUID, project_id): (int(total), int(completed), int(overdue))
            for project_id, total, completed, overdue in rows
        }

    async def _milestone_progress(self, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        rows = (
            await self.session.execute(
                select(ProjectMilestone.project_id, func.avg(ProjectMilestone.progress))
                .where(
                    ProjectMilestone.project_id.in_(project_ids),
                    ProjectMilestone.status != "cancelled",
                )
                .group_by(ProjectMilestone.project_id)
            )
        ).all()
        return {project_id: round(float(progress)) for project_id, progress in rows}

    async def _counts(self, column: Any, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        rows = (
            await self.session.execute(
                select(column, func.count()).where(column.in_(project_ids)).group_by(column)
            )
        ).all()
        return {project_id: int(count) for project_id, count in rows}

    async def _status_counts(
        self, model: Any, project_ids: list[uuid.UUID], statuses: set[str]
    ) -> dict[uuid.UUID, int]:
        rows = (
            await self.session.execute(
                select(model.project_id, func.count())
                .where(model.project_id.in_(project_ids), model.status.in_(statuses))
                .group_by(model.project_id)
            )
        ).all()
        return {project_id: int(count) for project_id, count in rows}

    async def _completion_warnings(self, project: Project) -> list[str]:
        warnings: list[str] = []
        if await self.session.scalar(
            select(func.count()).where(
                Task.project_id == project.id,
                Task.status.not_in(CLOSED_STATUSES),
                Task.deleted_at.is_(None),
            )
        ):
            warnings.append("incomplete tasks remain")
        if await self.session.scalar(
            select(func.count()).where(
                ProjectIssue.project_id == project.id,
                ProjectIssue.severity == "critical",
                ProjectIssue.status.not_in({"resolved", "closed"}),
            )
        ):
            warnings.append("critical issues remain open")
        if await self.session.scalar(
            select(func.count()).where(
                ProjectMilestone.project_id == project.id,
                ProjectMilestone.status.not_in({"completed", "cancelled"}),
            )
        ):
            warnings.append("milestones remain incomplete")
        return warnings

    async def _organization_references(
        self, actor: User, department_id: uuid.UUID | None, team_id: uuid.UUID | None
    ) -> None:
        if department_id and not await self.session.scalar(
            select(OrganizationUnit.id).where(
                OrganizationUnit.id == department_id,
                OrganizationUnit.organization_id == actor.organization_id,
                OrganizationUnit.deleted_at.is_(None),
            )
        ):
            raise NotFoundError("Department not found")
        if team_id:
            from meetinghq_api.modules.teams.models import Team

            if not await self.session.scalar(
                select(Team.id).where(
                    Team.id == team_id, Team.organization_id == actor.organization_id
                )
            ):
                raise NotFoundError("Team not found")

    async def _active_user(
        self, organization_id: uuid.UUID, user_id: uuid.UUID | None, *, allow_inactive: bool = False
    ) -> User:
        if user_id is None:
            raise NotFoundError("Employee not found")
        query = select(User).where(
            User.id == user_id, User.organization_id == organization_id, User.removed_at.is_(None)
        )
        if not allow_inactive:
            query = query.where(
                User.status == UserStatus.ACTIVE, User.employment_status != "terminated"
            )
        user = await self.session.scalar(query)
        if user is None:
            raise NotFoundError("Employee not found")
        return user

    async def _project_user(self, project: Project, user_id: uuid.UUID) -> User:
        user = await self._active_user(project.organization_id, user_id)
        if user.id != project.project_manager_id and not await self.session.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
            )
        ):
            raise ValidationError("Employee is not a project member")
        return user

    async def _member(self, project: Project, member_id: uuid.UUID) -> ProjectMember:
        row = await self.session.scalar(
            select(ProjectMember).where(
                ProjectMember.id == member_id,
                ProjectMember.project_id == project.id,
                ProjectMember.organization_id == project.organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Project member not found")
        return row

    async def _milestone(self, project: Project, milestone_id: uuid.UUID) -> ProjectMilestone:
        row = await self.session.scalar(
            select(ProjectMilestone).where(
                ProjectMilestone.id == milestone_id,
                ProjectMilestone.project_id == project.id,
                ProjectMilestone.organization_id == project.organization_id,
            )
        )
        if row is None:
            raise NotFoundError("Project milestone not found")
        return row

    async def _users(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = list(
            (
                await self.session.scalars(
                    select(User).where(User.organization_id == organization_id, User.id.in_(ids))
                )
            ).all()
        )
        return {row.id: row for row in rows}

    async def _event(
        self, actor: User, project: Project, event_type: str, payload: dict[str, object]
    ) -> None:
        await self.activity.publish(
            Activity(
                organization_id=actor.organization_id,
                actor_id=actor.id,
                event_type=event_type,
                subject_type="project",
                subject_id=project.id,
                payload={"project_code": project.project_code, "name": project.name, **payload},
            )
        )
        self.session.add(
            AuditLog(
                organization_id=actor.organization_id,
                user_id=actor.id,
                action=event_type,
                resource="project",
                resource_id=project.id,
                audit_metadata=payload,
            )
        )

    @staticmethod
    def _model(row: Any, response: type[Any]) -> dict[str, object]:
        return {key: getattr(row, key) for key in response.model_fields if hasattr(row, key)}

    @staticmethod
    def _value(value: object) -> object:
        return (
            str(value)
            if isinstance(value, uuid.UUID)
            else value.isoformat() if isinstance(value, (date, datetime)) else value
        )

    @staticmethod
    def _meeting_dict(row: Meeting) -> dict[str, object]:
        return {
            "id": str(row.id),
            "title": row.title,
            "start_datetime": row.start_datetime.isoformat(),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
