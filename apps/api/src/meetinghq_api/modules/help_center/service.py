"""Tenant-isolated knowledge management application service."""

import builtins
import uuid
from datetime import UTC, datetime

from sqlalchemy import Integer, String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.help_center.baseline_content import baseline_content
from meetinghq_api.modules.help_center.models import (
    HelpArticle,
    HelpInteraction,
    ProductTour,
    SupportRequest,
)
from meetinghq_api.modules.help_center.schemas import (
    HelpAnalyticsResponse,
    HelpArticleInput,
    HelpArticleUpdate,
    ProductTourInput,
    SupportRequestInput,
)
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError

ARTICLES: tuple[tuple[str, str, str, list[str]], ...] = (
    ("quick-start", "Quick Start Guide", "Getting Started", ["dashboard"]),
    ("installation", "Installation", "Getting Started", ["platform"]),
    ("first-login", "First Login", "Getting Started", ["login"]),
    ("dashboard", "Dashboard", "User Handbook", ["dashboard"]),
    ("my-space", "My Space", "User Handbook", ["my-space"]),
    ("projects", "Projects", "User Handbook", ["projects", "projects.detail"]),
    ("tasks-activities", "Tasks & Activities", "User Handbook", ["tasks", "activities"]),
    ("users", "Users", "Administrator Handbook", ["users", "members"]),
    ("roles-permissions", "Roles & Permissions", "Administrator Handbook", ["roles"]),
    ("meetings", "Meetings", "User Handbook", ["meetings", "meetings.detail", "meetings.new"]),
    ("calendar", "Calendar", "User Handbook", ["calendar"]),
    ("invitations", "Invitations", "Administrator Handbook", ["invitations"]),
    ("chat", "Chat", "User Handbook", ["chat", "chat.detail"]),
    ("people-directory", "People & Directory", "User Handbook", ["people", "employees"]),
    ("leave", "Leave Management", "User Handbook", ["leave"]),
    ("payroll", "Payroll & Payslips", "User Handbook", ["payroll"]),
    ("finance", "Finance Center", "User Handbook", ["finance"]),
    ("vouchers", "Vouchers", "User Handbook", ["vouchers"]),
    ("notifications", "Notifications", "User Handbook", ["notifications"]),
    ("email", "Email Delivery", "Administrator Handbook", ["mail"]),
    ("profile", "Profile & Security", "User Handbook", ["profile", "account"]),
    (
        "reporting-intelligence",
        "Reports & Management Intelligence",
        "User Handbook",
        ["reports", "reports.detail"],
    ),
    ("settings", "Organization Settings", "Administrator Handbook", ["settings", "organization"]),
    ("administration", "Administration", "Administrator Handbook", ["administration"]),
    ("integrations", "Integration Center", "Administrator Handbook", ["integrations"]),
    ("security", "Security & Access", "Administrator Handbook", ["security", "audit"]),
    ("keyboard-shortcuts", "Keyboard Shortcuts", "User Handbook", ["global"]),
    ("faq", "Frequently Asked Questions", "Troubleshooting", ["global"]),
    ("troubleshooting", "Troubleshooting", "Troubleshooting", ["health"]),
    ("whats-new", "What's New", "Release Notes", ["dashboard"]),
    ("release-notes", "Release Notes", "Release Notes", ["help"]),
    ("api-documentation", "API Guides", "API Guides", ["platform"]),
    ("deploy-gcp", "Deploy to Google Cloud", "Deployment Guides", ["platform"]),
    ("deploy-docker", "Deploy with Docker", "Deployment Guides", ["platform"]),
    ("deploy-kubernetes", "Kubernetes Deployment", "Deployment Guides", ["platform"]),
    ("backup-restore", "Backup & Restore", "Deployment Guides", ["administration"]),
    ("system-requirements", "System Requirements", "Deployment Guides", ["platform"]),
    ("employee-learning-path", "Employee Learning Path", "Learning Paths", []),
    ("manager-learning-path", "Manager Learning Path", "Learning Paths", []),
    (
        "project-manager-learning-path",
        "Project Manager Learning Path",
        "Learning Paths",
        [],
    ),
    ("finance-learning-path", "Finance / Accountant Learning Path", "Learning Paths", []),
    ("payroll-learning-path", "Payroll Officer Learning Path", "Learning Paths", []),
    (
        "people-admin-learning-path",
        "HR / People Administrator Learning Path",
        "Learning Paths",
        [],
    ),
    (
        "system-admin-learning-path",
        "System Administrator Learning Path",
        "Learning Paths",
        [],
    ),
)

BASELINE_KEYWORDS: dict[str, list[str]] = {
    "quick-start": ["access denied", "sidebar", "command centre", "quick create"],
    "first-login": ["change password", "temporary password", "sign in"],
    "projects": ["create project", "project report", "milestone", "risk", "issue"],
    "tasks-activities": ["create task", "daily activity", "reminder", "checklist"],
    "leave": ["request leave", "leave balance", "half day", "supporting document"],
    "vouchers": ["approve voucher", "disbursement", "separation of duties"],
    "finance": ["finance account", "transaction", "statement", "export statement"],
    "payroll": ["download payslip", "gross pay", "PAYE", "pension", "net pay"],
    "reporting-intelligence": ["submit weekly report", "monthly report", "project report"],
    "troubleshooting": ["cannot log in", "missing menu", "email not received"],
}

ADMIN_HELP_CATEGORIES = {"Administrator Handbook", "Deployment Guides", "API Guides"}


def baseline_permission(slug: str, category: str) -> str | None:
    if category in ADMIN_HELP_CATEGORIES or slug == "system-admin-learning-path":
        return "admin.manage"
    return None


class HelpCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_defaults(self, organization_id: uuid.UUID) -> None:
        existing = {
            row.slug: row
            for row in (
                await self.session.scalars(
                    select(HelpArticle).where(HelpArticle.organization_id == organization_id)
                )
            ).all()
        }
        for position, (slug, title, category, context_ids) in enumerate(ARTICLES):
            summary, content = baseline_content(slug, title, category)
            if slug in existing:
                article = existing[slug]
                if article.updated_by is None:
                    article.required_permission = baseline_permission(slug, category)
                    article.context_ids = context_ids
                    article.keywords = BASELINE_KEYWORDS.get(slug, [])
                    if not article.related_slugs:
                        article.related_slugs = (
                            ["troubleshooting"] if slug != "troubleshooting" else ["faq"]
                        )
                    if article.version == 1:
                        article.summary = summary
                        article.content = content
                continue
            self.session.add(
                HelpArticle(
                    organization_id=organization_id,
                    slug=slug,
                    title=title,
                    summary=summary,
                    category=category,
                    required_permission=baseline_permission(slug, category),
                    position=position,
                    content=content,
                    published=True,
                    workflow_status="published",
                    search_weight=100,
                    context_ids=context_ids,
                    keywords=BASELINE_KEYWORDS.get(slug, []),
                    related_slugs=["troubleshooting"] if slug != "troubleshooting" else ["faq"],
                )
            )
        await self.session.flush()

    async def list(
        self,
        organization_id: uuid.UUID,
        search: str | None = None,
        category: str | None = None,
        include_unpublished: bool = False,
        permissions: set[str] | None = None,
    ) -> list[HelpArticle]:
        await self.ensure_defaults(organization_id)
        query = select(HelpArticle).where(HelpArticle.organization_id == organization_id)
        if not include_unpublished:
            query = query.where(HelpArticle.workflow_status == "published")
            query = query.where(self._visibility(permissions or set()))
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    HelpArticle.title.ilike(term),
                    HelpArticle.summary.ilike(term),
                    HelpArticle.content.ilike(term),
                    HelpArticle.keywords.cast(String).ilike(term),
                )
            )
        if category:
            query = query.where(HelpArticle.category == category)
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        HelpArticle.search_weight.desc(),
                        HelpArticle.category,
                        HelpArticle.position,
                        HelpArticle.version.desc(),
                    )
                )
            ).all()
        )
        latest: dict[str, HelpArticle] = {}
        for row in rows:
            latest.setdefault(row.slug, row)
        return list(latest.values())

    async def get(
        self,
        organization_id: uuid.UUID,
        slug: str,
        user_id: uuid.UUID | None = None,
        include_unpublished: bool = False,
        permissions: set[str] | None = None,
    ) -> HelpArticle:
        await self.ensure_defaults(organization_id)
        query = (
            select(HelpArticle)
            .where(
                HelpArticle.organization_id == organization_id,
                HelpArticle.slug == slug,
            )
            .order_by(HelpArticle.version.desc())
        )
        if not include_unpublished:
            query = query.where(HelpArticle.workflow_status == "published")
            query = query.where(self._visibility(permissions or set()))
        article = await self.session.scalar(query)
        if article is None:
            raise NotFoundError("Help article not found")
        if user_id:
            await self.record_view(organization_id, article.id, user_id, permissions or set())
        return article

    async def versions(self, organization_id: uuid.UUID, slug: str) -> builtins.list[HelpArticle]:
        return list(
            (
                await self.session.scalars(
                    select(HelpArticle)
                    .where(
                        HelpArticle.organization_id == organization_id,
                        HelpArticle.slug == slug,
                    )
                    .order_by(HelpArticle.version.desc())
                )
            ).all()
        )

    async def create(
        self, organization_id: uuid.UUID, body: HelpArticleInput, actor_id: uuid.UUID
    ) -> HelpArticle:
        duplicate = await self.session.scalar(
            select(HelpArticle.id).where(
                HelpArticle.organization_id == organization_id,
                HelpArticle.slug == body.slug,
                HelpArticle.version == body.version,
            )
        )
        if duplicate:
            raise ConflictError("This article version already exists")
        values = body.model_dump()
        values["published"] = values["workflow_status"] == "published"
        article = HelpArticle(organization_id=organization_id, updated_by=actor_id, **values)
        self.session.add(article)
        self._audit(
            organization_id, actor_id, "help.article_created", article.id, {"slug": body.slug}
        )
        await self.session.flush()
        return article

    async def revise(
        self,
        organization_id: uuid.UUID,
        slug: str,
        body: HelpArticleUpdate,
        actor_id: uuid.UUID,
    ) -> HelpArticle:
        current = await self.get(organization_id, slug, include_unpublished=True)
        article = HelpArticle(
            organization_id=organization_id,
            slug=slug,
            version=current.version + 1,
            position=current.position,
            updated_by=actor_id,
            published=body.workflow_status == "published",
            **body.model_dump(),
        )
        self.session.add(article)
        self._audit(
            organization_id,
            actor_id,
            "help.article_revised",
            article.id,
            {"slug": slug, "version": article.version, "status": body.workflow_status},
        )
        await self.session.flush()
        return article

    async def resolve_context(
        self,
        organization_id: uuid.UUID,
        context_id: str,
        user_id: uuid.UUID,
        permissions: set[str],
    ) -> tuple[HelpArticle | None, ProductTour | None]:
        articles = await self.list(organization_id, permissions=permissions)
        candidates = [
            article
            for article in articles
            if context_id in article.context_ids or "global" in article.context_ids
        ]
        candidates.sort(
            key=lambda article: (context_id in article.context_ids, article.search_weight),
            reverse=True,
        )
        article = candidates[0] if candidates else None
        if article:
            await self.record_view(organization_id, article.id, user_id, permissions)
        tour = await self.session.scalar(
            select(ProductTour)
            .where(
                ProductTour.organization_id == organization_id,
                ProductTour.context_id == context_id,
                ProductTour.enabled.is_(True),
            )
            .order_by(ProductTour.version.desc())
        )
        return article, tour

    async def toggle_favorite(
        self,
        organization_id: uuid.UUID,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
        permissions: set[str],
    ) -> bool:
        article = await self._tenant_article(organization_id, article_id, permissions)
        interaction = await self._interaction(article, user_id)
        interaction.favorite = not interaction.favorite
        await self.session.flush()
        return interaction.favorite

    async def favorites(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, permissions: set[str]
    ) -> builtins.list[HelpArticle]:
        return list(
            (
                await self.session.scalars(
                    select(HelpArticle)
                    .join(HelpInteraction, HelpInteraction.article_id == HelpArticle.id)
                    .where(
                        HelpArticle.organization_id == organization_id,
                        HelpInteraction.user_id == user_id,
                        HelpInteraction.favorite.is_(True),
                        HelpArticle.workflow_status == "published",
                        self._visibility(permissions),
                    )
                    .order_by(HelpInteraction.last_viewed_at.desc())
                )
            ).all()
        )

    async def recent(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, permissions: set[str]
    ) -> builtins.list[HelpArticle]:
        return list(
            (
                await self.session.scalars(
                    select(HelpArticle)
                    .join(HelpInteraction, HelpInteraction.article_id == HelpArticle.id)
                    .where(
                        HelpArticle.organization_id == organization_id,
                        HelpInteraction.user_id == user_id,
                        HelpInteraction.last_viewed_at.is_not(None),
                        HelpArticle.workflow_status == "published",
                        self._visibility(permissions),
                    )
                    .order_by(HelpInteraction.last_viewed_at.desc())
                    .limit(12)
                )
            ).all()
        )

    async def record_view(
        self,
        organization_id: uuid.UUID,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
        permissions: set[str] | None = None,
    ) -> None:
        article = await self._tenant_article(organization_id, article_id, permissions)
        interaction = await self._interaction(article, user_id)
        interaction.view_count += 1
        interaction.last_viewed_at = datetime.now(UTC)
        await self.session.flush()

    async def analytics(self, organization_id: uuid.UUID) -> HelpAnalyticsResponse:
        article_count = await self.session.scalar(
            select(func.count(HelpArticle.id)).where(HelpArticle.organization_id == organization_id)
        )
        published_count = await self.session.scalar(
            select(func.count(HelpArticle.id)).where(
                HelpArticle.organization_id == organization_id,
                HelpArticle.workflow_status == "published",
            )
        )
        totals = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(HelpInteraction.view_count), 0),
                    func.count(func.distinct(HelpInteraction.user_id)),
                    func.coalesce(func.sum(HelpInteraction.favorite.cast(Integer)), 0),
                ).where(HelpInteraction.organization_id == organization_id)
            )
        ).one()
        popular = (
            await self.session.execute(
                select(
                    HelpArticle.slug,
                    HelpArticle.title,
                    func.sum(HelpInteraction.view_count).label("views"),
                )
                .join(HelpInteraction, HelpInteraction.article_id == HelpArticle.id)
                .where(HelpArticle.organization_id == organization_id)
                .group_by(HelpArticle.slug, HelpArticle.title)
                .order_by(func.sum(HelpInteraction.view_count).desc())
                .limit(10)
            )
        ).all()
        return HelpAnalyticsResponse(
            total_articles=int(article_count or 0),
            published_articles=int(published_count or 0),
            total_views=int(totals[0] or 0),
            unique_readers=int(totals[1] or 0),
            favorite_count=int(totals[2] or 0),
            popular_articles=[
                {"slug": row.slug, "title": row.title, "views": int(row.views or 0)}
                for row in popular
            ],
        )

    async def create_tour(
        self, organization_id: uuid.UUID, body: ProductTourInput, actor_id: uuid.UUID
    ) -> ProductTour:
        tour = ProductTour(
            organization_id=organization_id, created_by=actor_id, **body.model_dump()
        )
        self.session.add(tour)
        self._audit(
            organization_id,
            actor_id,
            "help.tour_created",
            tour.id,
            {"context_id": body.context_id},
        )
        await self.session.flush()
        return tour

    async def create_support_request(
        self,
        organization_id: uuid.UUID,
        requester_id: uuid.UUID,
        body: SupportRequestInput,
    ) -> SupportRequest:
        request_id = uuid.uuid4()
        reference = f"OF-{datetime.now(UTC):%Y%m%d}-{request_id.hex[:6].upper()}"
        safe_diagnostics = {
            key: value
            for key, value in body.diagnostics.items()
            if key in {"app_version", "browser", "viewport", "route"}
        }
        request = SupportRequest(
            id=request_id,
            organization_id=organization_id,
            requester_id=requester_id,
            reference=reference,
            request_type=body.request_type,
            priority=body.priority,
            subject=body.subject,
            description=body.description,
            status="open",
            page_url=body.page_url,
            module=body.module,
            diagnostics=safe_diagnostics,
        )
        self.session.add(request)
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=requester_id,
                action="support.request_created",
                resource="support_request",
                resource_id=request.id,
                audit_metadata={
                    "reference": reference,
                    "request_type": body.request_type,
                    "priority": body.priority,
                },
            )
        )
        await self.session.flush()
        return request

    async def support_requests(
        self,
        organization_id: uuid.UUID,
        requester_id: uuid.UUID,
        can_manage: bool,
    ) -> builtins.list[SupportRequest]:
        query = select(SupportRequest).where(SupportRequest.organization_id == organization_id)
        if not can_manage:
            query = query.where(SupportRequest.requester_id == requester_id)
        return list(
            (
                await self.session.scalars(
                    query.order_by(SupportRequest.created_at.desc()).limit(50)
                )
            ).all()
        )

    async def _tenant_article(
        self,
        organization_id: uuid.UUID,
        article_id: uuid.UUID,
        permissions: set[str] | None = None,
    ) -> HelpArticle:
        query = select(HelpArticle).where(
            HelpArticle.id == article_id,
            HelpArticle.organization_id == organization_id,
        )
        if permissions is not None:
            query = query.where(self._visibility(permissions))
        article = await self.session.scalar(query)
        if article is None:
            raise NotFoundError("Help article not found")
        return article

    @staticmethod
    def _visibility(permissions: set[str]) -> ColumnElement[bool]:
        if not permissions:
            return HelpArticle.required_permission.is_(None)
        return or_(
            HelpArticle.required_permission.is_(None),
            HelpArticle.required_permission.in_(permissions),
        )

    async def _interaction(self, article: HelpArticle, user_id: uuid.UUID) -> HelpInteraction:
        interaction = await self.session.scalar(
            select(HelpInteraction).where(
                HelpInteraction.article_id == article.id,
                HelpInteraction.user_id == user_id,
            )
        )
        if interaction is None:
            interaction = HelpInteraction(
                organization_id=article.organization_id,
                article_id=article.id,
                user_id=user_id,
                favorite=False,
                view_count=0,
            )
            self.session.add(interaction)
        return interaction

    def _audit(
        self,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        resource_id: uuid.UUID,
        metadata: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=actor_id,
                action=action,
                resource="help_article",
                resource_id=resource_id,
                audit_metadata=metadata,
            )
        )

    @staticmethod
    def _default_content(title: str, category: str) -> str:
        return baseline_content("", title, category)[1]
