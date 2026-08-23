"""Transactional internal event publisher and subscriber composition."""

from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.activity.models import ActivityEvent
from meetinghq_api.modules.events.models import DomainEventRecord
from meetinghq_api.shared.events import DomainEvent


class TransactionalDomainEventPublisher:
    """Persists business facts and projects user-facing activity transactionally."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, event: DomainEvent) -> None:
        self._session.add(
            DomainEventRecord(
                id=event.event_id,
                name=event.name,
                organization_id=event.organization_id,
                workspace_id=event.workspace_id,
                actor_id=event.actor_id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
                occurred_at=event.occurred_at,
            )
        )
        self._session.add(
            ActivityEvent(
                organization_id=event.organization_id,
                workspace_id=event.workspace_id,
                actor_id=event.actor_id,
                event_type=event.name,
                subject_type=event.aggregate_type,
                subject_id=event.aggregate_id,
                payload=event.payload,
            )
        )
