"""Workspace persistence adapter."""

import uuid
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.workspaces.models import Workspace
from meetinghq_api.shared.repository import SqlAlchemyRepository


class WorkspaceRepository(SqlAlchemyRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def get_for_organization(
        self, organization_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> Workspace | None:
        return cast(
            Workspace | None,
            await self.scalar(
                select(Workspace).where(
                    Workspace.id == workspace_id,
                    Workspace.organization_id == organization_id,
                    Workspace.deleted_at.is_(None),
                )
            ),
        )

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        archived: bool | None = None,
        classification: str | None = None,
    ) -> list[Workspace]:
        query = select(Workspace).where(
            Workspace.organization_id == organization_id,
            Workspace.deleted_at.is_(None),
        )
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(Workspace.name.ilike(term), Workspace.slug.ilike(term)))
        if archived is not None:
            query = query.where(
                Workspace.archived_at.is_not(None) if archived else Workspace.archived_at.is_(None)
            )
        if classification:
            query = query.where(Workspace.classification == classification)
        return list(
            await self.all(query.order_by(Workspace.archived_at.is_not(None), Workspace.name))
        )

    async def slug_exists(self, organization_id: uuid.UUID, slug: str) -> bool:
        return (
            await self.scalar(
                select(Workspace.id).where(
                    Workspace.organization_id == organization_id,
                    Workspace.slug == slug,
                    Workspace.deleted_at.is_(None),
                )
            )
            is not None
        )
