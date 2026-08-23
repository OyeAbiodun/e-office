"""Module-neutral domain event contracts."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """An immutable business fact published by an application service."""

    name: str
    organization_id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    payload: dict[str, object] = field(default_factory=dict)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DomainEventPublisher(Protocol):
    """Port implemented at the application composition boundary."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event within the current transaction."""
