"""Organization persistence adapter."""

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.shared.repository import SqlAlchemyRepository


class OrganizationRepository(SqlAlchemyRepository[Organization]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)

    async def get_active(self, organization_id: uuid.UUID) -> Organization | None:
        return cast(
            Organization | None,
            await self.scalar(
                select(Organization).where(
                    Organization.id == organization_id,
                    Organization.deleted_at.is_(None),
                )
            ),
        )

    async def slug_exists(self, slug: str) -> bool:
        organization_id = await self.scalar(
            select(Organization.id).where(Organization.slug == slug)
        )
        return organization_id is not None
