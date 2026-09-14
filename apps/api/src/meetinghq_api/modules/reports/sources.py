"""Batched adapters that project canonical work data into report snapshots."""

import uuid
from datetime import UTC, date, datetime, time
from typing import Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.finance.models import FinanceTransaction, Voucher
from meetinghq_api.modules.leave.models import LeaveRequest
from meetinghq_api.modules.meetings.models import (
    Meeting,
    MeetingActionItem,
    MeetingAttendee,
    MeetingDecision,
)
from meetinghq_api.modules.organizations.models import OrganizationUnit
from meetinghq_api.modules.payroll.models import PayrollEmployeeResult
from meetinghq_api.modules.projects.models import (
    Project,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectRisk,
    ProjectUpdate,
)
from meetinghq_api.modules.tasks.models import DailyActivity, Task
from meetinghq_api.modules.teams.models import Team, TeamMember
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError


class ReportSourceAdapter(Protocol):
    async def collect(
        self,
        organization_id: uuid.UUID,
        subject_id: uuid.UUID | None,
        start: date,
        end: date,
    ) -> tuple[
        str, uuid.UUID | None, uuid.UUID | None, dict[str, object], list[dict[str, object]]
    ]: ...


class WorkSourceAdapter:
    """Collect task, activity, project, and meeting data without copying sources."""

    def __init__(
        self,
        session: AsyncSession,
        subject_type: str,
        source_permissions: set[str] | None = None,
        requester_id: uuid.UUID | None = None,
    ) -> None:
        self.session = session
        self.subject_type = subject_type
        self.source_permissions = source_permissions or set()
        self.requester_id = requester_id

    async def collect(
        self,
        organization_id: uuid.UUID,
        subject_id: uuid.UUID | None,
        start: date,
        end: date,
    ) -> tuple[str, uuid.UUID | None, uuid.UUID | None, dict[str, object], list[dict[str, object]]]:
        subject_name, owner_id, manager_id, user_ids, project_id = await self._scope(
            organization_id, subject_id
        )
        start_at = datetime.combine(start, time.min, tzinfo=UTC)
        end_at = datetime.combine(end, time.max, tzinfo=UTC)
        task_query = select(Task).where(
            Task.organization_id == organization_id,
            Task.deleted_at.is_(None),
            or_(
                Task.created_at.between(start_at, end_at),
                Task.updated_at.between(start_at, end_at),
                Task.completed_at.between(start_at, end_at),
                Task.due_date.between(start, end),
            ),
        )
        activity_query = select(DailyActivity).where(
            DailyActivity.organization_id == organization_id,
            DailyActivity.deleted_at.is_(None),
            DailyActivity.activity_date.between(start, end),
        )
        project_query = select(Project).where(
            Project.organization_id == organization_id, Project.deleted_at.is_(None)
        )
        meeting_query = select(Meeting).where(
            Meeting.organization_id == organization_id,
            Meeting.start_datetime.between(start_at, end_at),
        )
        if project_id:
            task_query = task_query.where(Task.project_id == project_id)
            activity_query = activity_query.where(DailyActivity.project_id == project_id)
            project_query = project_query.where(Project.id == project_id)
            meeting_query = meeting_query.where(Meeting.project_id == project_id)
        elif self.subject_type != "management":
            # IN([]) deliberately evaluates false. Retaining the scope for an empty
            # team/department prevents an empty subject becoming organization-wide.
            task_query = task_query.where(Task.assignee_id.in_(user_ids))
            activity_query = activity_query.where(DailyActivity.user_id.in_(user_ids))
            project_query = project_query.where(
                or_(
                    Project.project_manager_id.in_(user_ids),
                    Project.id.in_(
                        select(ProjectMember.project_id).where(ProjectMember.user_id.in_(user_ids))
                    ),
                )
            )
            meeting_query = meeting_query.where(
                or_(
                    Meeting.organizer_id.in_(user_ids),
                    Meeting.id.in_(
                        select(MeetingAttendee.meeting_id).where(
                            MeetingAttendee.user_id.in_(user_ids)
                        )
                    ),
                )
            )
        tasks = list(
            (await self.session.scalars(task_query.order_by(Task.due_date, Task.id))).all()
        )
        activities = list(
            (await self.session.scalars(activity_query.order_by(DailyActivity.activity_date))).all()
        )
        projects = list((await self.session.scalars(project_query.order_by(Project.name))).all())
        meetings = list(
            (await self.session.scalars(meeting_query.order_by(Meeting.start_datetime))).all()
        )
        meeting_ids = {row.id for row in meetings}
        action_items = (
            list(
                (
                    await self.session.scalars(
                        select(MeetingActionItem).where(
                            MeetingActionItem.meeting_id.in_(meeting_ids),
                            or_(
                                MeetingActionItem.completed_at.between(start_at, end_at),
                                MeetingActionItem.due_date.between(start, end),
                            ),
                        )
                    )
                ).all()
            )
            if meeting_ids
            else []
        )
        decisions = (
            list(
                (
                    await self.session.scalars(
                        select(MeetingDecision).where(MeetingDecision.meeting_id.in_(meeting_ids))
                    )
                ).all()
            )
            if meeting_ids
            else []
        )
        project_ids = {row.id for row in projects}
        updates = (
            list(
                (
                    await self.session.scalars(
                        select(ProjectUpdate).where(
                            ProjectUpdate.organization_id == organization_id,
                            ProjectUpdate.project_id.in_(project_ids),
                            ProjectUpdate.reporting_date.between(start, end),
                        )
                    )
                ).all()
            )
            if project_ids
            else []
        )
        milestones = (
            list(
                (
                    await self.session.scalars(
                        select(ProjectMilestone).where(
                            ProjectMilestone.organization_id == organization_id,
                            ProjectMilestone.project_id.in_(project_ids),
                        )
                    )
                ).all()
            )
            if project_ids
            else []
        )
        risks = (
            list(
                (
                    await self.session.scalars(
                        select(ProjectRisk).where(
                            ProjectRisk.organization_id == organization_id,
                            ProjectRisk.project_id.in_(project_ids),
                            ProjectRisk.status.not_in({"closed"}),
                        )
                    )
                ).all()
            )
            if project_ids
            else []
        )
        issues = (
            list(
                (
                    await self.session.scalars(
                        select(ProjectIssue).where(
                            ProjectIssue.organization_id == organization_id,
                            ProjectIssue.project_id.in_(project_ids),
                            ProjectIssue.status.not_in({"resolved", "closed"}),
                        )
                    )
                ).all()
            )
            if project_ids
            else []
        )
        people = (
            list(
                (
                    await self.session.scalars(
                        select(User).where(
                            User.organization_id == organization_id,
                            User.id.in_(user_ids),
                            User.removed_at.is_(None),
                        )
                    )
                ).all()
            )
            if user_ids
            else []
        )
        task_progress: dict[uuid.UUID, int] = {}
        milestone_progress: dict[uuid.UUID, int] = {}
        if project_ids:
            task_progress_rows = (
                await self.session.execute(
                    select(
                        Task.project_id,
                        func.count(Task.id),
                        func.count(Task.id).filter(Task.status == "completed"),
                    )
                    .where(
                        Task.organization_id == organization_id,
                        Task.project_id.in_(project_ids),
                        Task.deleted_at.is_(None),
                    )
                    .group_by(Task.project_id)
                )
            ).all()
            task_progress = {
                project: round(int(completed) * 100 / int(total)) if total else 0
                for project, total, completed in task_progress_rows
                if project is not None
            }
            milestone_progress = {
                project: round(float(progress or 0))
                for project, progress in (
                    await self.session.execute(
                        select(ProjectMilestone.project_id, func.avg(ProjectMilestone.progress))
                        .where(
                            ProjectMilestone.organization_id == organization_id,
                            ProjectMilestone.project_id.in_(project_ids),
                        )
                        .group_by(ProjectMilestone.project_id)
                    )
                ).all()
            }
        sensitive = await self._sensitive_snapshot(
            organization_id, user_ids, start, end, subject_id
        )
        open_statuses = {"not_started", "in_progress", "blocked", "awaiting_review"}
        completed = [row for row in tasks if row.status == "completed"]
        overdue = [
            row
            for row in tasks
            if row.status in open_statuses and row.due_date and row.due_date < date.today()
        ]
        snapshot: dict[str, object] = {
            "summary": {
                "tasks_total": len(tasks),
                "tasks_completed": len(completed),
                "tasks_in_progress": sum(row.status == "in_progress" for row in tasks),
                "tasks_overdue": len(overdue),
                "activities": len(activities),
                "meetings": len(meetings),
                "decisions": len(decisions),
                "action_items": len(action_items),
                "projects": len(projects),
                "open_risks": len(risks),
                "open_issues": len(issues),
                "blockers": sum(bool(row.blockers) for row in activities)
                + sum(bool(row.blockers) for row in updates),
            },
            "tasks": [self._task(row) for row in tasks],
            "activities": [self._activity(row) for row in activities],
            "people": [self._person(row) for row in people],
            "projects": [
                self._project(
                    row,
                    (
                        row.manual_progress
                        if row.progress_mode == "manual"
                        else (
                            milestone_progress.get(row.id, 0)
                            if row.progress_mode == "milestone_based"
                            else task_progress.get(row.id, 0)
                        )
                    ),
                )
                for row in projects
            ],
            "meetings": [self._meeting(row) for row in meetings],
            "decisions": [self._decision(row) for row in decisions],
            "action_items": [self._action_item(row) for row in action_items],
            "milestones": [self._milestone(row) for row in milestones],
            "project_updates": [self._update(row) for row in updates],
            "risks": [self._attention(row) for row in risks],
            "issues": [self._attention(row) for row in issues],
            "upcoming_deadlines": [
                self._task(row)
                for row in tasks
                if row.status in open_statuses and row.due_date and row.due_date >= date.today()
            ][:25],
            **sensitive,
        }
        refs: list[dict[str, object]] = []
        refs.extend({"type": "task", "id": str(row.id)} for row in tasks)
        refs.extend({"type": "daily_activity", "id": str(row.id)} for row in activities)
        refs.extend({"type": "project", "id": str(row.id)} for row in projects)
        refs.extend({"type": "meeting", "id": str(row.id)} for row in meetings)
        refs.extend({"type": "meeting_decision", "id": str(row.id)} for row in decisions)
        refs.extend({"type": "meeting_action_item", "id": str(row.id)} for row in action_items)
        refs.extend({"type": "project_update", "id": str(row.id)} for row in updates)
        refs.extend({"type": "project_milestone", "id": str(row.id)} for row in milestones)
        refs.extend({"type": "project_risk", "id": str(row.id)} for row in risks)
        refs.extend({"type": "project_issue", "id": str(row.id)} for row in issues)
        return subject_name, owner_id, manager_id, snapshot, refs

    async def _sensitive_snapshot(
        self,
        organization_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        start: date,
        end: date,
        subject_id: uuid.UUID | None,
    ) -> dict[str, object]:
        snapshot: dict[str, object] = {}
        allow_leave = (
            self.subject_type == "employee"
            and (self.requester_id is None or self.requester_id == subject_id)
        ) or bool(self.source_permissions.intersection({"leave.view_team", "leave.reports.view"}))
        if allow_leave:
            leave_query = select(
                LeaveRequest.status, func.count(), func.sum(LeaveRequest.duration_days)
            ).where(
                LeaveRequest.organization_id == organization_id,
                LeaveRequest.deleted_at.is_(None),
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
            scoped_users = user_ids or (
                [subject_id] if self.subject_type == "employee" and subject_id else []
            )
            if self.subject_type != "management":
                leave_query = leave_query.where(LeaveRequest.employee_id.in_(scoped_users))
            leave_rows = (
                await self.session.execute(leave_query.group_by(LeaveRequest.status))
            ).all()
            snapshot["leave_context"] = [
                {"status": status, "requests": int(count), "days": str(days or 0)}
                for status, count, days in leave_rows
            ]
        if self.subject_type == "management" and self.source_permissions.intersection(
            {"vouchers.audit", "vouchers.disburse"}
        ):
            voucher_rows = (
                await self.session.execute(
                    select(Voucher.status, func.count(), func.sum(Voucher.requested_amount))
                    .where(
                        Voucher.organization_id == organization_id,
                        Voucher.created_at >= datetime.combine(start, time.min, tzinfo=UTC),
                        Voucher.created_at <= datetime.combine(end, time.max, tzinfo=UTC),
                        Voucher.deleted_at.is_(None),
                    )
                    .group_by(Voucher.status)
                )
            ).all()
            snapshot["voucher_indicators"] = [
                {"status": status, "count": int(count), "requested_amount": str(amount or 0)}
                for status, count, amount in voucher_rows
            ]
        if (
            self.subject_type == "management"
            and "finance.transactions.view" in self.source_permissions
        ):
            finance_rows = (
                await self.session.execute(
                    select(
                        FinanceTransaction.currency,
                        FinanceTransaction.direction,
                        func.sum(FinanceTransaction.amount),
                    )
                    .where(
                        FinanceTransaction.organization_id == organization_id,
                        FinanceTransaction.transaction_date.between(start, end),
                    )
                    .group_by(FinanceTransaction.currency, FinanceTransaction.direction)
                )
            ).all()
            snapshot["finance_indicators"] = [
                {"currency": currency, "direction": direction, "amount": str(amount or 0)}
                for currency, direction, amount in finance_rows
            ]
        if self.subject_type == "management" and "payroll.reports.view" in self.source_permissions:
            payroll = (
                await self.session.execute(
                    select(
                        PayrollEmployeeResult.currency,
                        func.count(),
                        func.sum(PayrollEmployeeResult.gross_pay),
                        func.sum(PayrollEmployeeResult.net_pay),
                    )
                    .where(PayrollEmployeeResult.organization_id == organization_id)
                    .group_by(PayrollEmployeeResult.currency)
                )
            ).all()
            snapshot["payroll_indicators"] = [
                {
                    "currency": currency,
                    "employees": int(employees),
                    "gross_pay": str(gross or 0),
                    "net_pay": str(net or 0),
                }
                for currency, employees, gross, net in payroll
            ]
        return snapshot

    async def _scope(
        self, organization_id: uuid.UUID, subject_id: uuid.UUID | None
    ) -> tuple[str, uuid.UUID | None, uuid.UUID | None, list[uuid.UUID], uuid.UUID | None]:
        if self.subject_type == "management":
            return "Organization management", None, None, [], None
        if subject_id is None:
            raise NotFoundError("Report subject not found")
        if self.subject_type == "employee":
            user = await self.session.scalar(
                select(User).where(User.id == subject_id, User.organization_id == organization_id)
            )
            if user is None:
                raise NotFoundError("Employee not found")
            return user.display_name, user.id, user.manager_id, [user.id], None
        if self.subject_type == "department":
            department = await self.session.scalar(
                select(OrganizationUnit).where(
                    OrganizationUnit.id == subject_id,
                    OrganizationUnit.organization_id == organization_id,
                    OrganizationUnit.deleted_at.is_(None),
                )
            )
            if department is None:
                raise NotFoundError("Department not found")
            users = list(
                (
                    await self.session.scalars(
                        select(User.id).where(
                            User.organization_id == organization_id,
                            User.department_id == department.id,
                            User.removed_at.is_(None),
                        )
                    )
                ).all()
            )
            return department.name, None, department.manager_id, users, None
        if self.subject_type == "team":
            team = await self.session.scalar(
                select(Team).where(Team.id == subject_id, Team.organization_id == organization_id)
            )
            if team is None:
                raise NotFoundError("Team not found")
            users = list(
                (
                    await self.session.scalars(
                        select(TeamMember.user_id).where(TeamMember.team_id == team.id)
                    )
                ).all()
            )
            return team.name, None, team.owner_id, users, None
        project = await self.session.scalar(
            select(Project).where(
                Project.id == subject_id,
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise NotFoundError("Project not found")
        return project.name, None, project.project_manager_id, [], project.id

    @staticmethod
    def _task(row: Task) -> dict[str, object]:
        return {
            "id": str(row.id),
            "title": row.title,
            "status": row.status,
            "priority": row.priority,
            "assignee_id": str(row.assignee_id),
            "project_id": str(row.project_id) if row.project_id else None,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }

    @staticmethod
    def _activity(row: DailyActivity) -> dict[str, object]:
        return {
            "id": str(row.id),
            "date": row.activity_date.isoformat(),
            "summary": row.summary,
            "outcome": row.outcome,
            "blockers": row.blockers,
            "next_step": row.next_step,
            "duration_minutes": row.duration_minutes,
            "task_id": str(row.task_id) if row.task_id else None,
            "project_id": str(row.project_id) if row.project_id else None,
            "meeting_id": str(row.meeting_id) if row.meeting_id else None,
        }

    @staticmethod
    def _project(row: Project, progress: int | None) -> dict[str, object]:
        return {
            "id": str(row.id),
            "code": row.project_code,
            "name": row.name,
            "status": row.status,
            "health": row.health,
            "progress": progress or 0,
            "target_end_date": row.target_end_date.isoformat() if row.target_end_date else None,
        }

    @staticmethod
    def _person(row: User) -> dict[str, object]:
        return {
            "id": str(row.id),
            "display_name": row.display_name,
            "job_title": row.job_title,
            "department_id": str(row.department_id) if row.department_id else None,
        }

    @staticmethod
    def _meeting(row: Meeting) -> dict[str, object]:
        return {
            "id": str(row.id),
            "title": row.title,
            "start_datetime": row.start_datetime.isoformat(),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "project_id": str(row.project_id) if row.project_id else None,
        }

    @staticmethod
    def _decision(row: MeetingDecision) -> dict[str, object]:
        return {
            "id": str(row.id),
            "meeting_id": str(row.meeting_id),
            "title": row.title,
            "description": row.description,
            "status": row.status,
        }

    @staticmethod
    def _action_item(row: MeetingActionItem) -> dict[str, object]:
        return {
            "id": str(row.id),
            "meeting_id": str(row.meeting_id),
            "title": row.title,
            "status": row.status,
            "assignee_id": str(row.assigned_to) if row.assigned_to else None,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }

    @staticmethod
    def _milestone(row: ProjectMilestone) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "name": row.name,
            "status": row.status,
            "progress": row.progress,
            "target_date": row.target_date.isoformat() if row.target_date else None,
        }

    @staticmethod
    def _update(row: ProjectUpdate) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "reporting_date": row.reporting_date.isoformat(),
            "summary": row.summary,
            "accomplishments": row.accomplishments,
            "blockers": row.blockers,
            "next_steps": row.next_steps,
        }

    @staticmethod
    def _attention(row: ProjectRisk | ProjectIssue) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "title": row.title,
            "severity": row.severity,
            "status": row.status,
        }
