"""Message delivery port, independent from message persistence."""

import uuid
from typing import Protocol


class MessageDelivery(Protocol):
    async def publish(self, conversation_id: uuid.UUID, event: dict[str, object]) -> None:
        """Deliver an already-persisted chat event."""


class NullMessageDelivery:
    async def publish(self, conversation_id: uuid.UUID, event: dict[str, object]) -> None:
        """Allow application services to run without an active transport."""
