"""Presence application service, independent from authentication."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.chat.models import Presence, PresenceStatus
from meetinghq_api.shared.events import DomainEvent


class PresenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = TransactionalDomainEventPublisher(session)

    async def set(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        status: PresenceStatus,
    ) -> Presence:
        presence = await self.session.get(Presence, user_id)
        if presence is None:
            presence = Presence(user_id=user_id)
            self.session.add(presence)
        presence.status = status
        presence.last_seen = datetime.now(UTC)
        await self.events.publish(
            DomainEvent(
                name="PresenceChanged",
                organization_id=organization_id,
                actor_id=user_id,
                aggregate_type="presence",
                aggregate_id=user_id,
                payload={"status": status},
            )
        )
        return presence

    async def list(self, organization_id: uuid.UUID) -> list[tuple[Presence, str]]:
        from meetinghq_api.modules.users.models import User

        rows = await self.session.execute(
            select(Presence, User.display_name)
            .join(User, User.id == Presence.user_id)
            .where(User.organization_id == organization_id)
            .order_by(User.display_name)
        )
        return list(rows.tuples().all())
