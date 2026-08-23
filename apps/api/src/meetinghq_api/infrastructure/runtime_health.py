"""Process-local health signals exposed to the administration health service."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class RuntimeHealth:
    """Small process registry for worker and scheduler liveness."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reminder_worker_started_at: datetime | None = None
    reminder_worker_heartbeat_at: datetime | None = None
    reminder_worker_last_error: str | None = None

    def worker_started(self) -> None:
        now = datetime.now(UTC)
        self.reminder_worker_started_at = now
        self.reminder_worker_heartbeat_at = now
        self.reminder_worker_last_error = None

    def worker_heartbeat(self) -> None:
        self.reminder_worker_heartbeat_at = datetime.now(UTC)
        self.reminder_worker_last_error = None

    def worker_failed(self, error: Exception) -> None:
        self.reminder_worker_heartbeat_at = datetime.now(UTC)
        self.reminder_worker_last_error = type(error).__name__


runtime_health = RuntimeHealth()
