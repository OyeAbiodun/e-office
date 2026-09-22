"""One-shot production worker entry point for scheduled MeetingHQ jobs."""

import asyncio

import structlog

from meetinghq_api.core.config import get_settings
from meetinghq_api.core.logging import configure_logging
from meetinghq_api.infrastructure.database import engine, session_factory
from meetinghq_api.infrastructure.redis import redis_client
from meetinghq_api.infrastructure.runtime_health import SharedRuntimeHealth
from meetinghq_api.modules.leave.service import LeaveService
from meetinghq_api.modules.mail.service import MailService
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.reports.service import ReportingService
from meetinghq_api.modules.tasks.service import TaskService

logger = structlog.get_logger(__name__)


async def run_once() -> int:
    """Claim and deliver one bounded batch of due meeting reminders."""
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")
    health = SharedRuntimeHealth(redis_client)
    try:
        await health.started()
        counts: dict[str, int] = {}
        async with session_factory() as session:
            service = NotificationService(session, settings)
            counts["meeting_invitations"] = await service.process_due_invitations()
            counts["meeting_reminders"] = await service.process_due_reminders()
            counts["browser_pushes"] = await service.process_due_browser_pushes()
            counts["task_reminders"] = await TaskService(session, service).process_due_reminders()
            counts["mail_deliveries"] = await MailService(
                session, settings
            ).process_due_deliveries()
            counts["leave_policies"] = await LeaveService(session).process_scheduled_policies()
            counts["scheduled_reports"] = await ReportingService(
                session, service
            ).process_scheduled_reports()
            await session.commit()
        delivered = sum(counts.values())
        await health.succeeded(counts)
        await logger.ainfo("scheduled_worker_completed", delivered=delivered)
        return delivered
    except Exception as error:
        try:
            await health.failed(error)
        except Exception:
            await logger.aexception("scheduled_worker_health_publish_failed")
        raise
    finally:
        await redis_client.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
