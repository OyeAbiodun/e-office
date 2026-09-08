"""FastAPI application composition root."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from meetinghq_api.api.v1.router import router as v1_router
from meetinghq_api.bootstrap import (
    BootstrapInitializationService,
    RbacInitializationService,
)
from meetinghq_api.core.config import get_settings
from meetinghq_api.core.logging import configure_logging
from meetinghq_api.core.middleware import (
    ApiEnvelopeMiddleware,
    MutationAuditMiddleware,
    SecurityHeadersMiddleware,
    install_error_handlers,
)
from meetinghq_api.infrastructure.database import engine, session_factory
from meetinghq_api.infrastructure.redis import redis_client
from meetinghq_api.infrastructure.runtime_health import runtime_health
from meetinghq_api.modules.integrations.service import IntegrationService
from meetinghq_api.modules.leave.service import LeaveService
from meetinghq_api.modules.mail.service import MailService
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.tasks.service import TaskService

logger = structlog.get_logger(__name__)


async def reminder_worker(stop: asyncio.Event) -> None:
    """Deliver due reminders until application shutdown."""
    settings = get_settings()
    runtime_health.worker_started()
    while not stop.is_set():
        try:
            async with session_factory() as session:
                service = NotificationService(session, settings)
                delivered = await service.process_due_invitations()
                delivered += await service.process_due_reminders()
                delivered += await service.process_due_browser_pushes()
                delivered += await TaskService(session, service).process_due_reminders()
                delivered += await MailService(session, settings).process_due_deliveries()
                delivered += await LeaveService(session).process_scheduled_policies()
                await session.commit()
            if delivered:
                await logger.ainfo("meeting_reminders_delivered", count=delivered)
            runtime_health.worker_heartbeat()
        except Exception as error:
            runtime_health.worker_failed(error)
            await logger.aexception("meeting_reminder_worker_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.reminder_poll_seconds)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage process-level infrastructure resources."""
    async with session_factory() as session:
        initialized = await BootstrapInitializationService(session, get_settings()).initialize()
        await RbacInitializationService(session).synchronize()
        sealed_credentials = await IntegrationService(
            session, get_settings()
        ).seal_legacy_credentials()
        await session.commit()
    if initialized:
        await logger.ainfo("installation_bootstrap_completed")
    if sealed_credentials:
        await logger.ainfo("legacy_integration_credentials_encrypted", count=sealed_credentials)
    reminder_stop = asyncio.Event()
    reminder_task = (
        asyncio.create_task(reminder_worker(reminder_stop))
        if get_settings().embedded_reminder_worker
        else None
    )
    await logger.ainfo("application_started")
    yield
    reminder_stop.set()
    if reminder_task is not None:
        await reminder_task
    await redis_client.aclose()
    await engine.dispose()
    await logger.ainfo("application_stopped")


def create_app() -> FastAPI:
    """Build and configure the MeetingHQ API."""
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")

    application = FastAPI(
        title="MeetingHQ API",
        summary="Schedule. Meet. Collaborate.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.audit_session_factory = session_factory
    application.state.environment = settings.environment
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(ApiEnvelopeMiddleware)
    application.add_middleware(MutationAuditMiddleware)
    install_error_handlers(application)
    application.include_router(v1_router, prefix="/api/v1")
    return application


app = create_app()
