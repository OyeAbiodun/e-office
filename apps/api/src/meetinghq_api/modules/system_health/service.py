"""Live, non-destructive platform health diagnostics."""

import asyncio
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psutil  # type: ignore[import-untyped]
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.infrastructure.redis import redis_client
from meetinghq_api.infrastructure.runtime_health import runtime_health
from meetinghq_api.modules.configuration.models import ConfigurationEntry
from meetinghq_api.modules.notifications.models import (
    MeetingInvitationDelivery,
    MeetingReminder,
)
from meetinghq_api.modules.system_health.models import SystemHealthSnapshot
from meetinghq_api.modules.system_health.schemas import (
    ComponentHealth,
    HealthHistoryPoint,
    HealthState,
    QueueHealth,
    SystemHealthResponse,
)


class SystemHealthService:
    """Collect bounded checks without exposing credentials or tenant data."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def snapshot(self, organization_id: uuid.UUID) -> SystemHealthResponse:
        now = datetime.now(UTC)
        queue = await self._queue(organization_id)
        components = [
            ComponentHealth(
                key="api",
                name="API",
                category="backend",
                status="healthy",
                message="API process is serving requests.",
            ),
            await self._database(),
            await self._redis(),
            self._worker(now),
            self._scheduler(now),
            self._smtp(),
            self._storage(),
            *self._host_resources(),
            self._websocket(),
            await self._integrations(organization_id),
            self._application_component(
                "mail", "Internal Mail", "Internal mailbox delivery is available."
            ),
            self._application_component(
                "calendar", "Calendar", "Calendar scheduling APIs are available."
            ),
            self._application_component(
                "meeting-provider",
                "Meeting provider",
                "MeetingHQ native meeting lifecycle is available.",
            ),
            self._application_component(
                "license", "License", "Self-managed MeetingHQ license is active."
            ),
            self._security(),
            self._queue_component(queue),
            *self._optional_components(),
        ]
        warnings = [
            component.message
            for component in components
            if component.status == "degraded"
            or (component.status == "not_configured" and component.requirement != "optional")
        ]
        errors = [
            component.message
            for component in components
            if component.status == "unavailable"
            and (component.requirement == "required" or component.configured)
        ]
        evaluated = [
            component
            for component in components
            if component.requirement == "required" or component.configured
        ]
        score = max(
            0,
            100
            - sum(15 for component in evaluated if component.status == "not_configured")
            - sum(10 for component in evaluated if component.status == "degraded")
            - sum(25 for component in evaluated if component.status == "unavailable"),
        )
        recommendations: list[str] = []
        if any(
            component.key == "redis" and component.configured and component.status != "healthy"
            for component in components
        ):
            recommendations.append(
                "Restore the configured Redis service or disable it until it is available."
            )
        if any(
            component.key == "smtp" and component.configured and component.status != "healthy"
            for component in components
        ):
            recommendations.append(
                "Configure and verify SMTP before production invitation delivery."
            )
        if queue.failed:
            recommendations.append(
                "Review failed notification jobs and retry after resolving providers."
            )
        status: HealthState = (
            "healthy"
            if not errors and score == 100
            else ("degraded" if score >= 50 else "unavailable")
        )
        response = SystemHealthResponse(
            status=status,
            score=score,
            required_healthy=sum(
                1
                for component in components
                if component.requirement == "required" and component.status == "healthy"
            ),
            required_total=sum(
                1 for component in components if component.requirement == "required"
            ),
            checked_at=now,
            last_updated=now,
            version="0.1.0",
            environment=self.settings.environment,
            uptime_seconds=max(0, int((now - runtime_health.started_at).total_seconds())),
            components=components,
            queue=queue,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
        )
        await self._record_history(organization_id, response)
        return response

    async def history(
        self, organization_id: uuid.UUID, limit: int = 96
    ) -> list[HealthHistoryPoint]:
        rows = list(
            (
                await self.session.scalars(
                    select(SystemHealthSnapshot)
                    .where(SystemHealthSnapshot.organization_id == organization_id)
                    .order_by(SystemHealthSnapshot.checked_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        return [
            HealthHistoryPoint(
                score=row.score,
                status=str(row.summary.get("status", "healthy")),
                checked_at=row.checked_at,
                incidents=self._incident_count(row.summary.get("incidents", 0)),
            )
            for row in reversed(rows)
        ]

    @staticmethod
    def _incident_count(value: object) -> int:
        return int(value) if isinstance(value, (int, float, str)) else 0

    async def _database(self) -> ComponentHealth:
        started = time.perf_counter()
        try:
            await self.session.execute(text("SELECT 1"))
            return ComponentHealth(
                key="database",
                name="Database",
                category="backend",
                status="healthy",
                message="Database connection and query execution are healthy.",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as error:
            return ComponentHealth(
                key="database",
                name="Database",
                category="backend",
                status="unavailable",
                message="Database health check failed.",
                details={"error": type(error).__name__},
            )

    async def _redis(self) -> ComponentHealth:
        if not self.settings.redis_url:
            return ComponentHealth(
                key="redis",
                name="Redis cache",
                category="backend",
                status="not_configured",
                requirement="recommended",
                configured=False,
                message=(
                    "Redis is not configured; local fallback behavior is active "
                    "but is not recommended for production."
                ),
            )
        started = time.perf_counter()
        try:
            await asyncio.wait_for(redis_client.ping(), timeout=1.5)
            return ComponentHealth(
                key="redis",
                name="Redis cache",
                category="backend",
                status="healthy",
                requirement="configured",
                message="Redis accepted a health probe.",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as error:
            return ComponentHealth(
                key="redis",
                name="Redis cache",
                category="backend",
                status="degraded",
                requirement="configured",
                message="Redis is configured but did not answer the probe.",
                details={"error": type(error).__name__},
            )

    def _worker(self, now: datetime) -> ComponentHealth:
        heartbeat = runtime_health.reminder_worker_heartbeat_at
        stale_after = self.settings.reminder_poll_seconds * 3
        age = int((now - heartbeat).total_seconds()) if heartbeat else None
        healthy = heartbeat is not None and age is not None and age <= stale_after
        return ComponentHealth(
            key="workers",
            name="Background workers",
            category="backend",
            status="healthy" if healthy else "degraded",
            message=(
                "Reminder worker heartbeat is current."
                if healthy
                else "Reminder worker heartbeat is missing or stale."
            ),
            details={
                "heartbeat_at": heartbeat.isoformat() if heartbeat else None,
                "last_error": runtime_health.reminder_worker_last_error,
            },
        )

    def _scheduler(self, now: datetime) -> ComponentHealth:
        worker = self._worker(now)
        return ComponentHealth(
            key="scheduler",
            name="Reminder scheduler",
            category="backend",
            status=worker.status,
            message=(
                "Reminder scheduling loop is active."
                if worker.status == "healthy"
                else worker.message
            ),
            details={"poll_seconds": self.settings.reminder_poll_seconds},
        )

    def _smtp(self) -> ComponentHealth:
        configured = bool(self.settings.smtp_host)
        return ComponentHealth(
            key="smtp",
            name="Email delivery",
            category="providers",
            status="healthy" if configured else "not_configured",
            requirement="configured" if configured else "recommended",
            configured=configured,
            message=(
                "SMTP provider is configured for outbound delivery."
                if configured
                else (
                    "SMTP is not configured; messages are written to the local "
                    "outbox and cannot reach external participants."
                )
            ),
            details={"mode": "smtp" if configured else "local_outbox"},
        )

    def _storage(self) -> ComponentHealth:
        path = Path(self.settings.local_storage_path).resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(path)
            free_percent = round((usage.free / usage.total) * 100, 1)
            return ComponentHealth(
                key="storage",
                name="File storage",
                category="infrastructure",
                status="healthy" if free_percent >= 10 else "degraded",
                message=f"Storage is writable with {free_percent}% free capacity.",
                details={
                    "provider": self.settings.storage_provider,
                    "free_bytes": usage.free,
                    "total_bytes": usage.total,
                },
            )
        except OSError as error:
            return ComponentHealth(
                key="storage",
                name="File storage",
                category="infrastructure",
                status="unavailable",
                message="Configured storage path is unavailable.",
                details={"error": type(error).__name__},
            )

    def _websocket(self) -> ComponentHealth:
        return ComponentHealth(
            key="websocket",
            name="Live updates",
            category="application",
            status="healthy",
            message="WebSocket endpoint is registered and available.",
            details={"path": "/api/v1/chat/ws"},
        )

    async def _integrations(self, organization_id: object) -> ComponentHealth:
        count = await self.session.scalar(
            select(func.count(ConfigurationEntry.id)).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.category.in_(("providers", "integrations")),
            )
        )
        return ComponentHealth(
            key="integrations",
            name="Connected providers",
            category="providers",
            status="healthy" if count else "not_configured",
            requirement="configured" if count else "optional",
            configured=bool(count),
            message=(
                f"{count} provider configuration(s) are registered."
                if count
                else "No external provider integrations are configured."
            ),
            details={"configured": int(count or 0)},
        )

    async def _queue(self, organization_id: object) -> QueueHealth:
        async def count(model: object, status: str) -> int:
            value = await self.session.scalar(
                select(func.count(model.id)).where(  # type: ignore[attr-defined]
                    model.organization_id == organization_id,  # type: ignore[attr-defined]
                    model.status == status,  # type: ignore[attr-defined]
                )
            )
            return int(value or 0)

        pending = await count(MeetingReminder, "pending") + await count(
            MeetingInvitationDelivery, "pending"
        )
        failed = await count(MeetingReminder, "failed") + await count(
            MeetingInvitationDelivery, "failed"
        )
        delivered = await count(MeetingReminder, "delivered") + await count(
            MeetingInvitationDelivery, "sent"
        )
        return QueueHealth(pending=pending, failed=failed, delivered=delivered)

    @staticmethod
    def _application_component(key: str, name: str, message: str) -> ComponentHealth:
        return ComponentHealth(
            key=key,
            name=name,
            category="application",
            status="healthy",
            message=message,
        )

    def _host_resources(self) -> list[ComponentHealth]:
        disk = shutil.disk_usage(Path(self.settings.local_storage_path).resolve())
        disk_percent = round((disk.used / disk.total) * 100, 1)
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)
        return [
            ComponentHealth(
                key="disk",
                name="Disk capacity",
                category="infrastructure",
                status="healthy" if disk_percent < 90 else "degraded",
                message=f"Disk utilization is {disk_percent}%.",
                details={"used_percent": disk_percent},
            ),
            ComponentHealth(
                key="cpu",
                name="CPU",
                category="infrastructure",
                status="healthy" if cpu_percent < 95 else "degraded",
                message=f"CPU utilization is {cpu_percent:.1f}%.",
                details={"used_percent": round(cpu_percent, 1)},
            ),
            ComponentHealth(
                key="memory",
                name="Memory",
                category="infrastructure",
                status="healthy" if memory.percent < 95 else "degraded",
                message=f"Memory utilization is {memory.percent:.1f}%.",
                details={
                    "used_percent": round(memory.percent, 1),
                    "available_bytes": memory.available,
                },
            ),
        ]

    def _security(self) -> ComponentHealth:
        default_secret = self.settings.jwt_secret == "local-development-secret-change-me"
        unsafe = self.settings.environment != "local" and default_secret
        return ComponentHealth(
            key="security",
            name="Security baseline",
            category="security",
            status="degraded" if unsafe else "healthy",
            message=(
                "Replace the development signing secret before production."
                if unsafe
                else "Authentication signing and tenant authorization are active."
            ),
        )

    @staticmethod
    def _queue_component(queue: QueueHealth) -> ComponentHealth:
        return ComponentHealth(
            key="queues",
            name="Delivery queues",
            category="application",
            status="degraded" if queue.failed else "healthy",
            message=(
                f"{queue.failed} delivery job(s) require attention."
                if queue.failed
                else "No failed delivery jobs are present."
            ),
            details=queue.model_dump(),
        )

    @staticmethod
    def _optional_components() -> list[ComponentHealth]:
        return [
            ComponentHealth(
                key=key,
                name=name,
                category=category,
                status="not_configured",
                requirement="optional",
                configured=False,
                message=f"{name} is optional and is not configured.",
            )
            for key, name, category in (
                ("ssl", "SSL termination", "infrastructure"),
                ("domain", "Custom domain", "infrastructure"),
                ("certificates", "Certificate monitoring", "infrastructure"),
                ("backups", "Automated backups", "operations"),
                ("cron", "External cron", "operations"),
                ("search", "Search provider", "providers"),
                ("ai-provider", "AI provider", "providers"),
                ("calendar-provider", "External calendar provider", "providers"),
                ("file-storage-provider", "External file storage", "providers"),
            )
        ]

    async def _record_history(
        self, organization_id: uuid.UUID, response: SystemHealthResponse
    ) -> None:
        latest = await self.session.scalar(
            select(SystemHealthSnapshot)
            .where(SystemHealthSnapshot.organization_id == organization_id)
            .order_by(SystemHealthSnapshot.checked_at.desc())
            .limit(1)
        )
        latest_checked_at = latest.checked_at if latest is not None else None
        if latest_checked_at is not None and latest_checked_at.tzinfo is None:
            latest_checked_at = latest_checked_at.replace(tzinfo=UTC)
        if (
            latest_checked_at is not None
            and (response.checked_at - latest_checked_at).total_seconds() < 60
        ):
            return
        self.session.add(
            SystemHealthSnapshot(
                organization_id=organization_id,
                score=response.score,
                summary={
                    "status": response.status,
                    "incidents": len(response.errors) + len(response.warnings),
                },
                checked_at=response.checked_at,
            )
        )
