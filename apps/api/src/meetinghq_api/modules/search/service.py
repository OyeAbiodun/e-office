"""Weighted, permission-aware global search."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.configuration.models import FeatureFlag
from meetinghq_api.modules.configuration.platform_service import PlatformService
from meetinghq_api.modules.help_center.models import HelpArticle
from meetinghq_api.modules.mail.models import MailMessage
from meetinghq_api.modules.meetings.models import Meeting, MeetingAttendee
from meetinghq_api.modules.notifications.models import Notification
from meetinghq_api.modules.search.schemas import SearchResponse, SearchResult
from meetinghq_api.modules.teams.models import Team
from meetinghq_api.modules.users.models import Role, User


class GlobalSearchService:
    """Search only resources visible in the authenticated tenant and permission context."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, user: User, query: str, limit: int) -> SearchResponse:
        term = query.strip()
        if len(term) < 2:
            return SearchResponse(query=term, results=[], total=0)
        pattern = f"%{term}%"
        permissions = {permission.name for role in user.roles for permission in role.permissions}
        results: list[SearchResult] = []
        results.extend(await self._navigation(user, term))
        if permissions & {"meetings.view", "meetings.read"}:
            results.extend(await self._meetings(user, pattern, permissions))
        if permissions & {"users.read", "users.view", "members.view"}:
            results.extend(await self._users(user, pattern))
        if permissions & {"teams.view", "teams.read"}:
            results.extend(await self._teams(user, pattern))
        if "roles.manage" in permissions or "admin.manage" in permissions:
            results.extend(await self._roles(user, pattern))
        if "mail.view" in permissions:
            results.extend(await self._mail(user, pattern))
        if "notifications.view" in permissions:
            results.extend(await self._notifications(user, pattern))
        results.extend(await self._help(user, pattern))
        if "admin.manage" in permissions:
            results.extend(await self._audit(user, pattern))
            results.extend(await self._integrations(user, pattern))
        ranked = sorted(
            results,
            key=lambda item: (
                -self._weighted_score(item, term),
                item.title.casefold(),
            ),
        )
        return SearchResponse(query=term, results=ranked[:limit], total=len(ranked))

    async def _navigation(self, user: User, term: str) -> list[SearchResult]:
        rows = await PlatformService(self.session).navigation(user)
        lowered = term.casefold()
        return [
            SearchResult(
                id=row.key,
                type="navigation",
                title=row.label,
                subtitle=f"{row.section.title()} navigation",
                url=row.path,
                icon=row.icon,
                score=100,
            )
            for row in rows
            if lowered in f"{row.label} {row.section}".casefold()
        ]

    async def _meetings(
        self, user: User, pattern: str, permissions: set[str]
    ) -> list[SearchResult]:
        query = select(Meeting).where(
            Meeting.organization_id == user.organization_id,
            or_(Meeting.title.ilike(pattern), Meeting.description.ilike(pattern)),
        )
        if "meetings.manage" not in permissions:
            attendee_meetings = select(MeetingAttendee.meeting_id).where(
                MeetingAttendee.user_id == user.id
            )
            query = query.where(
                or_(
                    Meeting.organizer_id == user.id,
                    Meeting.id.in_(attendee_meetings),
                    Meeting.visibility == "organization",
                )
            )
        rows = (await self.session.scalars(query.limit(8))).all()
        return [
            SearchResult(
                id=str(row.id),
                type="meeting",
                title=row.title,
                subtitle=f"{row.start_datetime:%b %d, %Y · %H:%M} · {row.status.value}",
                url=f"/meetings/{row.id}",
                icon="video",
                score=90,
            )
            for row in rows
        ]

    async def _users(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(User)
                .where(
                    User.organization_id == user.organization_id,
                    User.removed_at.is_(None),
                    or_(
                        User.display_name.ilike(pattern),
                        User.email.ilike(pattern),
                        User.department.ilike(pattern),
                    ),
                )
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="user",
                title=row.display_name,
                subtitle=" · ".join(
                    value for value in (row.job_title, row.department, row.email) if value
                ),
                url=f"/users/{row.id}",
                icon="users",
                score=85,
            )
            for row in rows
        ]

    async def _teams(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(Team)
                .where(
                    Team.organization_id == user.organization_id,
                    Team.deleted_at.is_(None),
                    or_(Team.name.ilike(pattern), Team.description.ilike(pattern)),
                )
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="team",
                title=row.name,
                subtitle=row.description or "Team collaboration space",
                url=f"/teams/{row.id}",
                icon="users",
                score=82,
            )
            for row in rows
        ]

    async def _roles(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(Role)
                .where(
                    Role.organization_id == user.organization_id,
                    or_(Role.name.ilike(pattern), Role.description.ilike(pattern)),
                )
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="role",
                title=row.name,
                subtitle=row.description or "Permission role",
                url="/roles",
                icon="shield",
                score=76,
            )
            for row in rows
        ]

    async def _mail(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(MailMessage)
                .where(
                    MailMessage.organization_id == user.organization_id,
                    MailMessage.owner_id == user.id,
                    MailMessage.deleted_at.is_(None),
                    or_(
                        MailMessage.subject.ilike(pattern),
                        MailMessage.from_name.ilike(pattern),
                        MailMessage.from_email.ilike(pattern),
                        MailMessage.body_text.ilike(pattern),
                    ),
                )
                .order_by(MailMessage.created_at.desc())
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="mail",
                title=row.subject or "(No subject)",
                subtitle=f"{row.from_name} · {row.preview}",
                url=f"/mail/{row.id}",
                icon="mail",
                score=80,
            )
            for row in rows
        ]

    async def _notifications(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(Notification)
                .where(
                    Notification.organization_id == user.organization_id,
                    Notification.user_id == user.id,
                    Notification.archived_at.is_(None),
                    or_(
                        Notification.title.ilike(pattern),
                        Notification.body.ilike(pattern),
                    ),
                )
                .order_by(Notification.delivered_at.desc())
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="notification",
                title=row.title,
                subtitle=row.body,
                url=row.action_url or "/notifications",
                icon="bell",
                score=74,
            )
            for row in rows
        ]

    async def _help(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(HelpArticle)
                .where(
                    HelpArticle.organization_id == user.organization_id,
                    HelpArticle.published.is_(True),
                    HelpArticle.workflow_status == "published",
                    or_(
                        HelpArticle.title.ilike(pattern),
                        HelpArticle.summary.ilike(pattern),
                        HelpArticle.content.ilike(pattern),
                    ),
                )
                .order_by(HelpArticle.search_weight.desc())
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="help",
                title=row.title,
                subtitle=f"{row.category} · {row.summary}",
                url=f"/help?article={row.slug}",
                icon="circle-help",
                score=min(88, 65 + row.search_weight // 10),
            )
            for row in rows
        ]

    async def _audit(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.organization_id == user.organization_id,
                    or_(AuditLog.action.ilike(pattern), AuditLog.resource.ilike(pattern)),
                )
                .order_by(AuditLog.created_at.desc())
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="audit",
                title=row.action.replace("_", " ").title(),
                subtitle=f"{row.resource} · {row.created_at:%b %d, %Y %H:%M}",
                url="/audit",
                icon="file-clock",
                score=62,
            )
            for row in rows
        ]

    async def _integrations(self, user: User, pattern: str) -> list[SearchResult]:
        rows = (
            await self.session.scalars(
                select(FeatureFlag)
                .where(
                    FeatureFlag.organization_id == user.organization_id,
                    FeatureFlag.installed.is_(True),
                    or_(
                        FeatureFlag.name.ilike(pattern),
                        FeatureFlag.description.ilike(pattern),
                    ),
                )
                .limit(8)
            )
        ).all()
        return [
            SearchResult(
                id=str(row.id),
                type="integration",
                title=row.name,
                subtitle=f"{row.availability_status.replace('_', ' ').title()} integration",
                url="/integrations",
                icon="plug",
                score=68,
            )
            for row in rows
        ]

    @staticmethod
    def _weighted_score(item: SearchResult, term: str) -> int:
        title = item.title.casefold()
        lowered = term.casefold()
        if title == lowered:
            return item.score + 50
        if title.startswith(lowered):
            return item.score + 25
        return item.score
