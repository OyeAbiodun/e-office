"""Reporting workflow, source orchestration, scheduling, and intelligence."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.activity.service import Activity, DatabaseActivityPublisher
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization, OrganizationUnit
from meetinghq_api.modules.projects.models import Project, ProjectMember
from meetinghq_api.modules.reports.models import (
    GeneratedReport,
    ReportPolicy,
    ReportReviewHistory,
    ReportVersion,
)
from meetinghq_api.modules.reports.schemas import (
    GenerateReportInput,
    NarrativeUpdate,
    PolicyResponse,
    PolicyUpdate,
    ReportDetail,
    ReportingDashboard,
    ReportPage,
    ReportResponse,
    ReportVersionResponse,
    ReviewHistoryResponse,
    ReviewInput,
)
from meetinghq_api.modules.reports.sources import WorkSourceAdapter
from meetinghq_api.modules.tasks.models import DailyActivity, Task
from meetinghq_api.modules.users.models import User, UserStatus
from meetinghq_api.shared.exceptions import AuthorizationError, ConflictError, NotFoundError

EDITABLE = {"generated_draft", "draft", "returned"}
SUBMITTABLE = {"generated_draft", "draft", "returned"}
REVIEWABLE = {"submitted", "auto_submitted"}


class ReportingService:
    def __init__(self, session: AsyncSession, notifications: NotificationService) -> None:
        self.session = session
        self.notifications = notifications
        self.activity = DatabaseActivityPublisher(session)

    @staticmethod
    def permissions(user: User) -> set[str]:
        return {permission.name for role in user.roles for permission in role.permissions}

    async def policy(self, actor: User) -> PolicyResponse:
        row = await self._policy(actor.organization_id)
        return PolicyResponse.model_validate(row)

    async def update_policy(self, actor: User, body: PolicyUpdate) -> PolicyResponse:
        row = await self._policy(actor.organization_id)
        before_auto = row.automatic_submit
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        row.updated_by_id = actor.id
        await self._event(
            actor.organization_id,
            actor.id,
            "report.policy_changed",
            row.id,
            {
                "automatic_submit": body.automatic_submit,
                "previous_automatic_submit": before_auto,
                "review_before_send": body.review_before_send,
                "timezone": body.timezone,
                "enabled_report_types": list(body.enabled_report_types),
            },
        )
        if before_auto != body.automatic_submit:
            await self._event(
                actor.organization_id,
                actor.id,
                (
                    "report.auto_submit_enabled"
                    if body.automatic_submit
                    else "report.auto_submit_disabled"
                ),
                row.id,
                {"enabled": body.automatic_submit},
            )
        return PolicyResponse.model_validate(row)

    async def preview_sources(self, actor: User, start: date, end: date) -> dict[str, object]:
        _, _, _, snapshot, refs = await WorkSourceAdapter(
            self.session, "employee", requester_id=actor.id
        ).collect(actor.organization_id, actor.id, start, end)
        return {"snapshot": snapshot, "source_refs": refs}

    async def generate(self, actor: User, body: GenerateReportInput) -> ReportResponse:
        await self._authorize_generation(actor, body)
        return await self._generate(
            actor.organization_id,
            actor.id,
            body,
            source_permissions=self.permissions(actor),
        )

    async def _generate(
        self,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        body: GenerateReportInput,
        source_permissions: set[str] | None = None,
    ) -> ReportResponse:
        policy = await self._policy(organization_id)
        key = (
            f"{body.report_type}:{body.subject_id or organization_id}:{body.period_type}:"
            f"{body.period_start}:{body.period_end}"
            if body.scheduled
            else None
        )
        if key:
            existing = await self.session.scalar(
                select(GeneratedReport).where(
                    GeneratedReport.organization_id == organization_id,
                    GeneratedReport.generation_key == key,
                )
            )
            if existing:
                return ReportResponse.model_validate(existing)
        subject_name, owner_id, manager_id, snapshot, refs = await WorkSourceAdapter(
            self.session,
            body.report_type,
            source_permissions
            or ({"leave.view_own"} if body.scheduled and body.report_type == "employee" else set()),
            requester_id=actor_id,
        ).collect(organization_id, body.subject_id, body.period_start, body.period_end)
        policy_snapshot = self._policy_snapshot(policy)
        row = GeneratedReport(
            organization_id=organization_id,
            report_type=body.report_type,
            subject_type=body.report_type,
            subject_id=body.subject_id,
            subject_name=subject_name,
            owner_id=owner_id,
            manager_id=manager_id,
            period_type=body.period_type,
            period_start=body.period_start,
            period_end=body.period_end,
            timezone=policy.timezone,
            status="generated_draft",
            generation_key=key,
            authoritative_snapshot=snapshot,
            narrative=self._initial_narrative(snapshot),
            source_refs=refs,
            policy_snapshot=policy_snapshot,
            generated_by_id=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        await self._version(row, actor_id)
        await self._history(row, actor_id, "generated", None)
        await self._event(
            organization_id,
            actor_id,
            "report.generated",
            row.id,
            {"report_type": body.report_type, "scheduled": body.scheduled},
        )
        if owner_id:
            await self._notify(
                organization_id,
                owner_id,
                "report.generated",
                "Report ready for review",
                f"Your {body.period_type} report for {body.period_start} through "
                f"{body.period_end} is ready.",
                row.id,
            )
        return ReportResponse.model_validate(row)

    async def list_reports(
        self,
        actor: User,
        *,
        search: str | None,
        report_type: str | None,
        subject_id: uuid.UUID | None,
        period_type: str | None,
        status: str | None,
        period_start: date | None,
        period_end: date | None,
        page: int,
        page_size: int,
    ) -> ReportPage:
        query = select(GeneratedReport).where(
            GeneratedReport.organization_id == actor.organization_id
        )
        query = self._visible_query(actor, query)
        if search:
            query = query.where(GeneratedReport.subject_name.ilike(f"%{search.strip()}%"))
        if report_type:
            query = query.where(GeneratedReport.report_type == report_type)
        if subject_id:
            query = query.where(GeneratedReport.subject_id == subject_id)
        if period_type:
            query = query.where(GeneratedReport.period_type == period_type)
        if status:
            query = query.where(
                GeneratedReport.status.in_(REVIEWABLE)
                if status == "pending_review"
                else GeneratedReport.status == status
            )
        if period_start:
            query = query.where(GeneratedReport.period_end >= period_start)
        if period_end:
            query = query.where(GeneratedReport.period_start <= period_end)
        total = int(
            await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        )
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(GeneratedReport.created_at.desc(), GeneratedReport.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return ReportPage(
            items=[ReportResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
        )

    async def detail(self, actor: User, report_id: uuid.UUID) -> ReportDetail:
        report = await self._visible(actor, report_id)
        versions = list(
            (
                await self.session.scalars(
                    select(ReportVersion)
                    .where(
                        ReportVersion.report_id == report.id,
                        ReportVersion.organization_id == actor.organization_id,
                    )
                    .order_by(ReportVersion.version.desc())
                )
            ).all()
        )
        history = list(
            (
                await self.session.scalars(
                    select(ReportReviewHistory)
                    .where(
                        ReportReviewHistory.report_id == report.id,
                        ReportReviewHistory.organization_id == actor.organization_id,
                    )
                    .order_by(ReportReviewHistory.created_at.desc())
                )
            ).all()
        )
        return ReportDetail(
            report=ReportResponse.model_validate(report),
            versions=[ReportVersionResponse.model_validate(row) for row in versions],
            history=[ReviewHistoryResponse.model_validate(row) for row in history],
        )

    async def edit(
        self, actor: User, report_id: uuid.UUID, body: NarrativeUpdate
    ) -> ReportResponse:
        report = await self._visible(actor, report_id)
        if report.owner_id != actor.id and "reports.generate" not in self.permissions(actor):
            raise AuthorizationError("You cannot edit this report")
        if report.status not in EDITABLE:
            raise ConflictError("Submitted and final reports cannot be edited")
        report.narrative = {**report.narrative, **body.model_dump(exclude_none=True)}
        report.version += 1
        report.status = "draft"
        report.return_reason = None
        await self._version(report, actor.id)
        await self._history(report, actor.id, "edited", None)
        await self._event(
            actor.organization_id, actor.id, "report.edited", report.id, {"version": report.version}
        )
        return ReportResponse.model_validate(report)

    async def submit(self, actor: User, report_id: uuid.UUID) -> ReportResponse:
        report = await self._visible(actor, report_id)
        if report.owner_id != actor.id:
            raise AuthorizationError("You cannot submit this report")
        if report.status not in SUBMITTABLE:
            raise ConflictError("Report is not ready for submission")
        if not str(report.narrative.get("accomplishments") or "").strip():
            raise ConflictError("Add an accomplishment or work summary before submitting")
        return ReportResponse.model_validate(
            await self._submit(
                report, actor.id, automatic=False, policy=await self._policy(actor.organization_id)
            )
        )

    async def review(self, actor: User, report_id: uuid.UUID, body: ReviewInput) -> ReportResponse:
        report = await self._visible(actor, report_id)
        if report.status not in REVIEWABLE:
            raise ConflictError("Report is not awaiting review")
        if report.manager_id != actor.id and "reports.review_team" not in self.permissions(actor):
            raise AuthorizationError("You cannot review this report")
        now = datetime.now(UTC)
        report.reviewer_id = actor.id
        report.reviewed_at = now
        report.review_comment = body.comment
        if body.action == "return":
            report.status = "returned"
            report.return_reason = body.comment
            action = "returned"
            if report.owner_id:
                await self._notify(
                    actor.organization_id,
                    report.owner_id,
                    "report.returned",
                    "Report returned for correction",
                    body.comment or "Your manager requested corrections.",
                    report.id,
                )
        else:
            report.status = "final"
            report.finalized_at = now
            report.return_reason = None
            action = "finalized"
            if report.owner_id:
                await self._notify(
                    actor.organization_id,
                    report.owner_id,
                    "report.finalized",
                    "Report finalized",
                    f"Your {report.period_type} report was reviewed and finalized.",
                    report.id,
                )
        await self._history(report, actor.id, action, body.comment)
        await self._event(
            actor.organization_id,
            actor.id,
            f"report.{action}",
            report.id,
            {"version": report.version},
        )
        return ReportResponse.model_validate(report)

    async def dashboard(self, actor: User) -> ReportingDashboard:
        permissions = self.permissions(actor)
        base = GeneratedReport.organization_id == actor.organization_id
        visible = self._visible_query(actor, select(GeneratedReport.id)).subquery()
        status_rows = (
            await self.session.execute(
                select(GeneratedReport.status, func.count())
                .where(base, GeneratedReport.id.in_(select(visible.c.id)))
                .group_by(GeneratedReport.status)
            )
        ).all()
        statuses: dict[str, int] = {key: int(value) for key, value in status_rows}
        total = sum(int(value) for value in statuses.values())
        final = int(statuses.get("final", 0))
        own_drafts = int(
            await self.session.scalar(
                select(func.count(GeneratedReport.id)).where(
                    GeneratedReport.organization_id == actor.organization_id,
                    GeneratedReport.owner_id == actor.id,
                    GeneratedReport.status.in_(EDITABLE),
                )
            )
            or 0
        )
        task_scope = [
            Task.organization_id == actor.organization_id,
            Task.deleted_at.is_(None),
        ]
        if "reports.view_management" not in permissions:
            if "reports.view_department" in permissions and actor.department_id:
                task_scope.append(Task.department_id == actor.department_id)
            elif "reports.view_team" in permissions:
                task_scope.append(
                    or_(
                        Task.assignee_id == actor.id,
                        Task.assignee_id.in_(
                            select(User.id).where(
                                User.organization_id == actor.organization_id,
                                User.manager_id == actor.id,
                            )
                        ),
                    )
                )
            else:
                task_scope.append(Task.assignee_id == actor.id)
        task_rows = (
            await self.session.execute(
                select(Task.status, func.count()).where(*task_scope).group_by(Task.status)
            )
        ).all()
        task_counts: dict[str, int] = {key: int(value) for key, value in task_rows}
        overdue = int(
            await self.session.scalar(
                select(func.count(Task.id)).where(
                    *task_scope,
                    Task.status.in_({"not_started", "in_progress", "blocked", "awaiting_review"}),
                    Task.due_date < date.today(),
                )
            )
            or 0
        )
        project_scope = [
            Project.organization_id == actor.organization_id,
            Project.deleted_at.is_(None),
            Project.archived_at.is_(None),
        ]
        if "reports.view_management" not in permissions:
            project_scope.append(
                or_(
                    Project.project_manager_id == actor.id,
                    Project.id.in_(
                        select(ProjectMember.project_id).where(
                            ProjectMember.organization_id == actor.organization_id,
                            ProjectMember.user_id == actor.id,
                        )
                    ),
                )
            )
        health_rows = (
            await self.session.execute(
                select(Project.health, func.count()).where(*project_scope).group_by(Project.health)
            )
        ).all()
        project_health: dict[str, int] = {key: int(value) for key, value in health_rows}
        dept_rows: list[tuple[str, int]] = []
        if "reports.view_management" in permissions or (
            "reports.view_department" in permissions and actor.department_id
        ):
            department_query = (
                select(OrganizationUnit.name, func.count(DailyActivity.id))
                .outerjoin(
                    DailyActivity,
                    and_(
                        DailyActivity.department_id == OrganizationUnit.id,
                        DailyActivity.deleted_at.is_(None),
                    ),
                )
                .where(
                    OrganizationUnit.organization_id == actor.organization_id,
                    OrganizationUnit.deleted_at.is_(None),
                )
                .group_by(OrganizationUnit.id, OrganizationUnit.name)
                .order_by(func.count(DailyActivity.id).desc())
                .limit(10)
            )
            if "reports.view_management" not in permissions:
                department_query = department_query.where(
                    OrganizationUnit.id == actor.department_id
                )
            dept_rows = [
                (name, int(count))
                for name, count in (await self.session.execute(department_query)).all()
            ]
        return ReportingDashboard(
            pending_my_review=own_drafts,
            awaiting_manager_review=int(
                statuses.get("submitted", 0) + statuses.get("auto_submitted", 0)
            ),
            returned=int(statuses.get("returned", 0)),
            finalized_this_period=final,
            reporting_compliance_percent=round(final * 100 / total) if total else 100,
            active_projects=sum(
                int(value) for key, value in project_health.items() if key != "completed"
            ),
            projects_at_risk=int(
                project_health.get("at_risk", 0) + project_health.get("off_track", 0)
            ),
            open_tasks=sum(
                int(task_counts.get(key, 0))
                for key in {"not_started", "in_progress", "blocked", "awaiting_review"}
            ),
            overdue_tasks=overdue,
            unresolved_blockers=int(task_counts.get("blocked", 0)),
            department_activity=[
                {"department": name, "activities": count} for name, count in dept_rows
            ],
        )

    async def process_scheduled_reports(
        self,
        today: date | None = None,
        now: datetime | None = None,
        *,
        force_generation: bool = False,
    ) -> int:
        clock = now or datetime.now(UTC)
        organization_ids = list((await self.session.scalars(select(Organization.id))).all())
        policies = [await self._policy(organization_id) for organization_id in organization_ids]
        generated = 0
        for policy in policies:
            local_now = clock.astimezone(ZoneInfo(policy.timezone))
            local_today = today or local_now.date()
            if (
                today is None
                and not force_generation
                and local_now.timetz().replace(tzinfo=None) < policy.generation_time
            ):
                continue
            users = list(
                (
                    await self.session.scalars(
                        select(User).where(
                            User.organization_id == policy.organization_id,
                            User.status == UserStatus.ACTIVE,
                            User.removed_at.is_(None),
                            User.employment_status != "terminated",
                        )
                    )
                ).all()
            )
            periods: list[tuple[Literal["daily", "weekly", "monthly"], date, date]] = []
            if policy.daily_enabled and "daily" in policy.enabled_report_types:
                previous_day = local_today - timedelta(days=1)
                periods.append(("daily", previous_day, previous_day))
            if policy.weekly_enabled and "weekly" in policy.enabled_report_types:
                week_end = local_today - timedelta(
                    days=(local_today.weekday() - policy.week_end) % 7
                )
                periods.append(("weekly", week_end - timedelta(days=6), week_end))
            if (
                policy.monthly_enabled
                and "monthly" in policy.enabled_report_types
                and local_today.day <= 3
            ):
                month_end = local_today.replace(day=1) - timedelta(days=1)
                periods.append(("monthly", month_end.replace(day=1), month_end))
            for period_type, start, end in periods:
                for user in users:
                    before = await self.session.scalar(
                        select(GeneratedReport.id).where(
                            GeneratedReport.organization_id == policy.organization_id,
                            GeneratedReport.generation_key
                            == f"employee:{user.id}:{period_type}:{start}:{end}",
                        )
                    )
                    await self._generate(
                        policy.organization_id,
                        None,
                        GenerateReportInput(
                            report_type="employee",
                            subject_id=user.id,
                            period_type=period_type,
                            period_start=start,
                            period_end=end,
                            scheduled=True,
                        ),
                    )
                    generated += int(before is None)
        await self.process_submission_deadlines(clock)
        return generated

    async def process_submission_deadlines(self, now: datetime | None = None) -> int:
        """Send one deadline reminder or auto-submit according to the stored policy."""
        now = now or datetime.now(UTC)
        reports = list(
            (
                await self.session.scalars(
                    select(GeneratedReport).where(
                        GeneratedReport.generation_key.is_not(None),
                        GeneratedReport.status.in_(SUBMITTABLE),
                    )
                )
            ).all()
        )
        processed = 0
        for report in reports:
            policy = await self._policy(report.organization_id)
            local_zone = ZoneInfo(policy.timezone)
            local_deadline = datetime.combine(
                report.period_end, policy.generation_time, tzinfo=local_zone
            ) + timedelta(hours=policy.submission_deadline_hours)
            deadline = local_deadline.astimezone(UTC)
            if policy.automatic_submit and now >= deadline:
                await self._submit(report, None, automatic=True, policy=policy)
                processed += 1
                continue
            reminder_at = deadline - timedelta(hours=policy.reminder_hours_before)
            if (
                report.owner_id
                and report.submission_reminder_sent_at is None
                and reminder_at <= now < deadline
            ):
                await self._notify(
                    report.organization_id,
                    report.owner_id,
                    "report.submission_due",
                    "Report submission is due soon",
                    f"Your {report.period_type} report is due by {deadline.isoformat()}.",
                    report.id,
                )
                report.submission_reminder_sent_at = now
                await self._event(
                    report.organization_id,
                    None,
                    "report.submission_reminder_sent",
                    report.id,
                    {"deadline": deadline.isoformat()},
                )
                processed += 1
        return processed

    async def _submit(
        self,
        report: GeneratedReport,
        actor_id: uuid.UUID | None,
        *,
        automatic: bool,
        policy: ReportPolicy,
    ) -> GeneratedReport:
        now = datetime.now(UTC)
        report.submission_mode = "automatic" if automatic else "manual"
        report.submitted_at = now
        if policy.manager_review_required and report.manager_id:
            report.status = "auto_submitted" if automatic else "submitted"
            await self._notify(
                report.organization_id,
                report.manager_id,
                "report.submitted",
                "Report awaiting review",
                f"{report.subject_name}'s {report.period_type} report is ready for review.",
                report.id,
            )
        else:
            report.status = "final"
            report.finalized_at = now
        await self._version(report, actor_id)
        await self._history(report, actor_id, report.status, None)
        await self._event(
            report.organization_id,
            actor_id,
            "report.auto_submitted" if automatic else "report.submitted",
            report.id,
            {"submission_mode": report.submission_mode, "version": report.version},
        )
        return report

    async def _authorize_generation(self, actor: User, body: GenerateReportInput) -> None:
        permissions = self.permissions(actor)
        if body.report_type == "employee" and body.subject_id == actor.id:
            if not permissions.intersection({"reports.create_own", "reports.generate"}):
                raise AuthorizationError("You cannot generate reports")
            return
        required = {
            "employee": {"reports.generate", "reports.view_team", "reports.view_department"},
            "team": {"reports.generate", "reports.view_team"},
            "department": {"reports.generate", "reports.view_department"},
            "project": {"reports.generate", "projects.generate_reports"},
            "management": {"reports.view_management"},
        }[body.report_type]
        if not permissions.intersection(required):
            raise AuthorizationError("You cannot generate this report")
        if "reports.view_management" in permissions or "reports.generate" in permissions:
            return
        if body.report_type == "employee":
            target = await self.session.scalar(
                select(User).where(
                    User.id == body.subject_id,
                    User.organization_id == actor.organization_id,
                    User.removed_at.is_(None),
                )
            )
            if target is None:
                raise NotFoundError("Employee not found")
            same_department = bool(
                actor.department_id
                and target.department_id == actor.department_id
                and "reports.view_department" in permissions
            )
            if target.manager_id != actor.id and not same_department:
                raise AuthorizationError("You cannot generate a report for this employee")
        elif body.report_type == "team" and body.subject_id != actor.team_id:
            raise AuthorizationError("You cannot generate a report for this team")
        elif body.report_type == "department" and body.subject_id != actor.department_id:
            raise AuthorizationError("You cannot generate a report for this department")
        elif body.report_type == "project":
            project = await self.session.scalar(
                select(Project).where(
                    Project.id == body.subject_id,
                    Project.organization_id == actor.organization_id,
                    Project.deleted_at.is_(None),
                )
            )
            if project is None:
                raise NotFoundError("Project not found")
            membership = await self.session.scalar(
                select(ProjectMember.id).where(
                    ProjectMember.organization_id == actor.organization_id,
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == actor.id,
                )
            )
            if project.project_manager_id != actor.id and membership is None:
                raise AuthorizationError("You cannot generate a report for this project")

    def _visible_query(self, actor: User, query: Select[Any]) -> Select[Any]:
        permissions = self.permissions(actor)
        if "reports.view_management" in permissions:
            return query
        rules = [GeneratedReport.owner_id == actor.id, GeneratedReport.manager_id == actor.id]
        if "reports.view_department" in permissions and actor.department_id:
            rules.append(
                GeneratedReport.subject_id.in_(
                    select(User.id).where(
                        User.organization_id == actor.organization_id,
                        User.department_id == actor.department_id,
                    )
                )
            )
            rules.append(GeneratedReport.subject_id == actor.department_id)
        if "reports.view_team" in permissions and actor.team_id:
            rules.append(GeneratedReport.subject_id == actor.team_id)
        rules.append(
            and_(
                GeneratedReport.subject_type == "project",
                GeneratedReport.subject_id.in_(
                    select(ProjectMember.project_id).where(
                        ProjectMember.organization_id == actor.organization_id,
                        ProjectMember.user_id == actor.id,
                    )
                ),
            )
        )
        return query.where(or_(*rules))

    async def _visible(self, actor: User, report_id: uuid.UUID) -> GeneratedReport:
        query = select(GeneratedReport).where(
            GeneratedReport.id == report_id,
            GeneratedReport.organization_id == actor.organization_id,
        )
        report = await self.session.scalar(self._visible_query(actor, query))
        if report is None:
            raise NotFoundError("Report not found")
        return report  # type: ignore[no-any-return]

    async def _policy(self, organization_id: uuid.UUID) -> ReportPolicy:
        row = await self.session.scalar(
            select(ReportPolicy).where(ReportPolicy.organization_id == organization_id)
        )
        if row is None:
            organization = await self.session.get(Organization, organization_id)
            row = ReportPolicy(
                organization_id=organization_id,
                timezone=organization.timezone if organization else "UTC",
            )
            self.session.add(row)
            await self.session.flush()
        return row

    async def _version(self, report: GeneratedReport, actor_id: uuid.UUID | None) -> None:
        existing = await self.session.scalar(
            select(ReportVersion.id).where(
                ReportVersion.report_id == report.id, ReportVersion.version == report.version
            )
        )
        if existing is None:
            self.session.add(
                ReportVersion(
                    organization_id=report.organization_id,
                    report_id=report.id,
                    version=report.version,
                    snapshot=report.authoritative_snapshot,
                    narrative=report.narrative,
                    created_by_id=actor_id,
                )
            )

    async def _history(
        self, report: GeneratedReport, actor_id: uuid.UUID | None, action: str, note: str | None
    ) -> None:
        self.session.add(
            ReportReviewHistory(
                organization_id=report.organization_id,
                report_id=report.id,
                actor_id=actor_id,
                action=action,
                note=note,
            )
        )

    async def _event(
        self,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        event_type: str,
        report_id: uuid.UUID,
        metadata: dict[str, object],
    ) -> None:
        await self.activity.publish(
            Activity(
                organization_id=organization_id,
                actor_id=actor_id,
                event_type=event_type,
                subject_type="report",
                subject_id=report_id,
                payload=metadata,
            )
        )
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=actor_id,
                action=event_type,
                resource="report",
                resource_id=report_id,
                audit_metadata=metadata,
            )
        )

    async def _notify(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str,
        report_id: uuid.UUID,
    ) -> None:
        await self.notifications.create_notification(
            organization_id=organization_id,
            user_id=user_id,
            notification_type=kind,
            category="reports",
            priority="normal",
            title=title,
            body=body,
            action_url=f"/reports/{report_id}",
            metadata={"report_id": str(report_id)},
        )

    @staticmethod
    def _policy_snapshot(row: ReportPolicy) -> dict[str, object]:
        return {
            "review_before_send": row.review_before_send,
            "automatic_submit": row.automatic_submit,
            "manager_review_required": row.manager_review_required,
            "submission_deadline_hours": row.submission_deadline_hours,
            "timezone": row.timezone,
        }

    @staticmethod
    def _initial_narrative(snapshot: dict[str, object]) -> dict[str, object]:
        updates = snapshot.get("project_updates", [])
        activities = snapshot.get("activities", [])
        return {
            "accomplishments": "\n".join(
                str(item.get("accomplishments") or item.get("outcome") or item.get("summary"))
                for item in [*updates, *activities]  # type: ignore[misc]
                if item.get("accomplishments") or item.get("outcome") or item.get("summary")
            ),
            "challenges": "\n".join(
                str(item.get("blockers"))
                for item in [*updates, *activities]  # type: ignore[misc]
                if item.get("blockers")
            ),
            "next_priorities": "\n".join(
                str(item.get("next_steps") or item.get("next_step"))
                for item in [*updates, *activities]  # type: ignore[misc]
                if item.get("next_steps") or item.get("next_step")
            ),
        }
