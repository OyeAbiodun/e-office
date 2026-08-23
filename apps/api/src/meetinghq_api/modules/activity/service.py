"""Activity publication contract and database adapter."""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.activity.models import ActivityEvent


@dataclass(frozen=True, slots=True)
class Activity:
    """Module-independent activity publication request."""

    organization_id: uuid.UUID
    actor_id: uuid.UUID | None
    event_type: str
    subject_type: str
    subject_id: uuid.UUID | None
    workspace_id: uuid.UUID | None = None
    payload: dict[str, object] = field(default_factory=dict)


class ActivityPublisher(Protocol):
    """Port consumed by business modules."""

    async def publish(self, activity: Activity) -> None:
        """Persist or dispatch an activity."""


class DatabaseActivityPublisher:
    """Transaction-aware activity persistence adapter."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, activity: Activity) -> None:
        self._session.add(
            ActivityEvent(
                organization_id=activity.organization_id,
                workspace_id=activity.workspace_id,
                actor_id=activity.actor_id,
                event_type=activity.event_type,
                subject_type=activity.subject_type,
                subject_id=activity.subject_id,
                payload=activity.payload,
            )
        )
