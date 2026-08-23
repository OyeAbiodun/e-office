"""Reusable soft-deletion model behavior."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """Adds reversible, actor-attributed deletion to an entity."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)

    def soft_delete(self, actor_id: uuid.UUID) -> None:
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = actor_id

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None
