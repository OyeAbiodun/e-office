"""Background job ports for future worker infrastructure."""

from datetime import datetime
from typing import Protocol


class BackgroundJobScheduler(Protocol):
    async def enqueue(self, job: str, payload: dict[str, object]) -> str: ...
    async def schedule(self, job: str, run_at: datetime, payload: dict[str, object]) -> str: ...


CALENDAR_JOB_NAMES = frozenset(
    {
        "calendar.reminder.schedule",
        "calendar.synchronize",
        "calendar.expired.cleanup",
        "ai.process",
    }
)
