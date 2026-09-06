"""One-shot production worker entry point for scheduled MeetingHQ jobs."""

import asyncio

import structlog

from meetinghq_api.core.config import get_settings
from meetinghq_api.core.logging import configure_logging
from meetinghq_api.infrastructure.database import engine, session_factory
from meetinghq_api.infrastructure.redis import redis_client
from meetinghq_api.modules.mail.service import MailService
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.tasks.service import TaskService

logger = structlog.get_logger(__name__)


async def run_once() -> int:
    """Claim and deliver one bounded batch of due meeting reminders."""
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")
    try:
        async with session_factory() as session:
            service = NotificationService(session, settings)
            delivered = await service.process_due_invitations()
            delivered += await service.process_due_reminders()
            delivered += await service.process_due_browser_pushes()
            delivered += await TaskService(session, service).process_due_reminders()
            delivered += await MailService(session, settings).process_due_deliveries()
            await session.commit()
        await logger.ainfo("scheduled_worker_completed", delivered=delivered)
        return delivered
    finally:
        await redis_client.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
