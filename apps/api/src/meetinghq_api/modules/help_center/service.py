"""Tenant-isolated knowledge management application service."""

import builtins
import uuid
from datetime import UTC, datetime

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.help_center.models import (
    HelpArticle,
    HelpInteraction,
    ProductTour,
)
from meetinghq_api.modules.help_center.schemas import (
    HelpAnalyticsResponse,
    HelpArticleInput,
    HelpArticleUpdate,
    ProductTourInput,
)
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError

ARTICLES = (
    ("quick-start", "Quick Start Guide", "Getting Started", ["dashboard"]),
    ("installation", "Installation", "Getting Started", ["administration"]),
    ("first-login", "First Login", "Getting Started", ["login"]),
    ("dashboard", "Dashboard", "User Handbook", ["dashboard"]),
    ("users", "Users", "Administrator Handbook", ["users", "members"]),
    ("roles-permissions", "Roles & Permissions", "Administrator Handbook", ["roles"]),
    ("meetings", "Meetings", "User Handbook", ["meetings", "meetings.detail", "meetings.new"]),
    ("calendar", "Calendar", "User Handbook", ["calendar"]),
    ("invitations", "Invitations", "Administrator Handbook", ["invitations"]),
    ("chat", "Chat", "User Handbook", ["chat", "chat.detail"]),
    ("notifications", "Notifications", "User Handbook", ["notifications"]),
    ("email", "Email Delivery", "Administrator Handbook", ["mail"]),
    ("profile", "Profile & Security", "User Handbook", ["profile", "account"]),
    ("settings", "Organization Settings", "Administrator Handbook", ["settings", "organization"]),
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
)


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
            if slug in existing:
                article = existing[slug]
                if not article.context_ids:
                    article.context_ids = context_ids
                if not article.related_slugs:
                    article.related_slugs = (
                        ["troubleshooting"] if slug != "troubleshooting" else ["faq"]
                    )
                continue
            self.session.add(
                HelpArticle(
                    organization_id=organization_id,
                    slug=slug,
                    title=title,
                    summary=f"Learn how MeetingHQ {title.lower()} works.",
                    category=category,
                    position=position,
                    content=self._default_content(title, category),
                    published=True,
                    workflow_status="published",
                    search_weight=100,
                    context_ids=context_ids,
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
    ) -> list[HelpArticle]:
        await self.ensure_defaults(organization_id)
        query = select(HelpArticle).where(HelpArticle.organization_id == organization_id)
        if not include_unpublished:
            query = query.where(HelpArticle.workflow_status == "published")
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    HelpArticle.title.ilike(term),
                    HelpArticle.summary.ilike(term),
                    HelpArticle.content.ilike(term),
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
        article = await self.session.scalar(query)
        if article is None:
            raise NotFoundError("Help article not found")
        if user_id:
            await self.record_view(organization_id, article.id, user_id)
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
        self, organization_id: uuid.UUID, context_id: str, user_id: uuid.UUID
    ) -> tuple[HelpArticle | None, ProductTour | None]:
        articles = await self.list(organization_id)
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
            await self.record_view(organization_id, article.id, user_id)
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
        self, organization_id: uuid.UUID, article_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        article = await self._tenant_article(organization_id, article_id)
        interaction = await self._interaction(article, user_id)
        interaction.favorite = not interaction.favorite
        await self.session.flush()
        return interaction.favorite

    async def favorites(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
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
                    )
                    .order_by(HelpInteraction.last_viewed_at.desc())
                )
            ).all()
        )

    async def recent(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
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
                    )
                    .order_by(HelpInteraction.last_viewed_at.desc())
                    .limit(12)
                )
            ).all()
        )

    async def record_view(
        self, organization_id: uuid.UUID, article_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        article = await self._tenant_article(organization_id, article_id)
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

    async def _tenant_article(
        self, organization_id: uuid.UUID, article_id: uuid.UUID
    ) -> HelpArticle:
        article = await self.session.scalar(
            select(HelpArticle).where(
                HelpArticle.id == article_id,
                HelpArticle.organization_id == organization_id,
            )
        )
        if article is None:
            raise NotFoundError("Help article not found")
        return article

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
        return (
            f"# {title}\n\n"
            f"This {category.lower()} article explains {title.lower()} in MeetingHQ.\n\n"
            "## Before you begin\n\n"
            "- Sign in with your MeetingHQ account.\n"
            "- Confirm the required menu is visible for your assigned role.\n"
            "- Contact an administrator if a required permission is unavailable.\n\n"
            "## Procedure\n\n"
            f"1. Open the relevant MeetingHQ workspace for **{title}**.\n"
            "2. Complete the required fields and review the visible validation guidance.\n"
            "3. Save the change and confirm the success state.\n\n"
            "```text\nTip: Press Ctrl+K to open MeetingHQ search.\n```\n\n"
            "> Settings and menu availability are controlled by your administrator.\n\n"
            "## Need more help?\n\n"
            "Search Troubleshooting or contact your MeetingHQ administrator."
        )
