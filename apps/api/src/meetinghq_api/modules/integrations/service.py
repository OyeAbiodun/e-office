"""Tenant-safe provider configuration and connectivity service."""

import asyncio
import builtins
import imaplib
import smtplib
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.core.secrets import SecretVault
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.configuration.models import ConfigurationEntry, FeatureFlag
from meetinghq_api.modules.configuration.platform_service import PlatformService
from meetinghq_api.modules.configuration.schemas import ConfigurationUpdate
from meetinghq_api.modules.integrations.registry import (
    PROVIDER_MAP,
    PROVIDERS,
    ProviderDefinition,
)
from meetinghq_api.modules.integrations.schemas import (
    IntegrationResponse,
    IntegrationTestResponse,
)
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError


class IntegrationService:
    """Keep provider secrets out of Platform Management."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.vault = SecretVault((settings or get_settings()).jwt_secret)

    async def list(self, organization_id: uuid.UUID) -> list[IntegrationResponse]:
        await PlatformService(self.session).ensure_defaults(organization_id)
        flags = {
            item.key: item
            for item in (
                await self.session.scalars(
                    select(FeatureFlag).where(FeatureFlag.organization_id == organization_id)
                )
            ).all()
        }
        configurations = {
            item.key.removeprefix("integration."): item
            for item in (
                await self.session.scalars(
                    select(ConfigurationEntry).where(
                        ConfigurationEntry.organization_id == organization_id,
                        ConfigurationEntry.category == "integrations",
                    )
                )
            ).all()
        }
        statuses = {
            item.key.removeprefix("integration-status."): item
            for item in (
                await self.session.scalars(
                    select(ConfigurationEntry).where(
                        ConfigurationEntry.organization_id == organization_id,
                        ConfigurationEntry.category == "integration-status",
                    )
                )
            ).all()
        }
        return [
            self._response(
                provider.key,
                self._enabled(flags.get(provider.key)),
                configurations.get(provider.key),
                statuses.get(provider.key),
            )
            for provider in PROVIDERS
        ]

    async def configure(
        self,
        organization_id: uuid.UUID,
        key: str,
        values: dict[str, object],
        actor: User,
    ) -> IntegrationResponse:
        self._provider(key)
        await PlatformService(self.session).set_configuration(
            organization_id,
            f"integration.{key}",
            ConfigurationUpdate(
                value=self.vault.seal(values),
                category="integrations",
                is_secret=True,
            ),
            actor,
        )
        await self.session.flush()
        await self._set_status(
            organization_id,
            key,
            "attention",
            "Credentials are stored but the connection has not been validated.",
            actor,
            checked_at=None,
        )
        self._audit(
            organization_id,
            actor.id,
            "integrations.configured",
            key,
            {"status": "configured"},
        )
        rows = await self.list(organization_id)
        return next(item for item in rows if item.key == key)

    async def seal_legacy_credentials(self) -> int:
        """Encrypt provider records created before the credential vault existed."""
        rows = (
            await self.session.scalars(
                select(ConfigurationEntry).where(
                    ConfigurationEntry.category == "integrations",
                    ConfigurationEntry.is_secret.is_(True),
                )
            )
        ).all()
        updated = 0
        for entry in rows:
            if entry.value and not self.vault.is_sealed(entry.value):
                entry.value = self.vault.seal(dict(entry.value))
                updated += 1
        if updated:
            await self.session.flush()
        return updated

    async def disconnect(self, organization_id: uuid.UUID, key: str, actor: User) -> None:
        self._provider(key)
        entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == f"integration.{key}",
            )
        )
        if entry is not None:
            await self.session.delete(entry)
        status_entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == f"integration-status.{key}",
            )
        )
        if status_entry is not None:
            await self.session.delete(status_entry)
        self._audit(
            organization_id,
            actor.id,
            "integrations.disconnected",
            key,
            {"status": "disconnected"},
        )

    async def test_connection(
        self, organization_id: uuid.UUID, key: str, actor: User
    ) -> IntegrationTestResponse:
        provider = self._provider(key)
        entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == f"integration.{key}",
            )
        )
        if entry is None or not entry.value:
            raise NotFoundError("Configure this provider before testing its connection")
        values = self.vault.open(dict(entry.value))
        started = time.perf_counter()
        try:
            message = await self._probe(provider, values)
            result_status: Literal["healthy", "attention"] = "healthy"
        except Exception as error:
            message = f"Connection failed: {str(error)[:240]}"
            result_status = "attention"
        response = IntegrationTestResponse(
            key=key,
            status=result_status,
            message=message,
            latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
            checked_at=datetime.now(UTC),
        )
        await self._set_status(
            organization_id,
            key,
            response.status,
            response.message,
            actor,
            checked_at=response.checked_at,
        )
        self._audit(
            organization_id,
            actor.id,
            "integrations.connection_tested",
            key,
            {
                "status": response.status,
                "latency_ms": response.latency_ms,
            },
        )
        return response

    async def synchronize(self, organization_id: uuid.UUID, key: str, actor: User) -> None:
        self._provider(key)
        entry = await self.session.scalar(
            select(ConfigurationEntry.id).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == f"integration.{key}",
            )
        )
        if entry is None:
            raise NotFoundError("Configure this provider before synchronization")
        status_entry = await self.session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == f"integration-status.{key}",
            )
        )
        status_value = status_entry.value if status_entry is not None else {}
        if not isinstance(status_value, dict) or status_value.get("status") != "healthy":
            raise ConflictError("Validate this provider connection before synchronization")
        self._audit(
            organization_id,
            actor.id,
            "integrations.synchronization_requested",
            key,
            {"status": "queued"},
        )

    async def audit_history(self, organization_id: uuid.UUID, key: str) -> Sequence[AuditLog]:
        self._provider(key)
        rows = builtins.list(
            (
                await self.session.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.organization_id == organization_id,
                        AuditLog.resource == "integration",
                    )
                    .order_by(AuditLog.created_at.desc())
                    .limit(200)
                )
            ).all()
        )
        return [
            row
            for row in rows
            if isinstance(row.audit_metadata, dict) and row.audit_metadata.get("provider") == key
        ][:50]

    def _audit(
        self,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        key: str,
        metadata: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=actor_id,
                action=action,
                resource="integration",
                resource_id=None,
                audit_metadata={"provider": key, **metadata},
            )
        )

    async def _probe(self, provider: ProviderDefinition, values: dict[str, object]) -> str:
        if provider.auth_type == "smtp":
            await asyncio.to_thread(self._probe_smtp, values)
            return "SMTP authentication and NOOP completed successfully."
        if provider.auth_type == "imap":
            await asyncio.to_thread(self._probe_imap, values)
            return "IMAP authentication completed successfully."
        endpoint = self._endpoint(provider, values)
        headers: dict[str, str] = {}
        token = values.get("token") or values.get("api_key")
        if isinstance(token, str) and token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
        return f"{provider.name} endpoint responded with HTTP {response.status_code}."

    @staticmethod
    def _probe_smtp(values: dict[str, object]) -> None:
        host = str(values.get("host") or "")
        if not host:
            raise ValueError("SMTP host is required")
        port = IntegrationService._port(values.get("port"), 587)
        with smtplib.SMTP(host, port, timeout=10) as client:
            if values.get("starttls", True):
                client.starttls()
            username = values.get("username")
            if isinstance(username, str) and username:
                client.login(username, str(values.get("password") or ""))
            client.noop()

    @staticmethod
    def _probe_imap(values: dict[str, object]) -> None:
        host = str(values.get("host") or "")
        if not host:
            raise ValueError("IMAP host is required")
        port = IntegrationService._port(values.get("port"), 993)
        with imaplib.IMAP4_SSL(host, port, timeout=10) as client:
            client.login(
                str(values.get("username") or ""),
                str(values.get("password") or ""),
            )

    @staticmethod
    def _endpoint(provider: ProviderDefinition, values: dict[str, object]) -> str:
        configured = values.get("endpoint") or values.get("base_url") or values.get("server_url")
        if isinstance(configured, str) and configured.startswith(("https://", "http://")):
            return configured
        discovery = {
            "microsoft-365": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
            "google-workspace": "https://accounts.google.com/.well-known/openid-configuration",
            "gmail": "https://accounts.google.com/.well-known/openid-configuration",
            "outlook": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
            "yahoo": "https://api.login.yahoo.com/.well-known/openid-configuration",
        }
        endpoint = discovery.get(provider.key)
        if endpoint is None:
            raise ValueError("A provider endpoint is required for connection testing")
        return endpoint

    @staticmethod
    def _port(value: object, default: int) -> int:
        return int(value) if isinstance(value, (int, str)) else default

    def _response(
        self,
        key: str,
        enabled: bool,
        configuration: ConfigurationEntry | None,
        status_entry: ConfigurationEntry | None,
    ) -> IntegrationResponse:
        provider = self._provider(key)
        configured = configuration is not None and bool(configuration.value)
        status_value = status_entry.value if status_entry is not None else {}
        status = status_value.get("status") if isinstance(status_value, dict) else None
        checked_at_value = (
            status_value.get("checked_at") if isinstance(status_value, dict) else None
        )
        try:
            last_tested_at = (
                datetime.fromisoformat(str(checked_at_value)) if checked_at_value else None
            )
        except ValueError:
            last_tested_at = None
        validated = configured and status == "healthy"
        return IntegrationResponse(
            key=provider.key,
            name=provider.name,
            category=provider.category,
            description=provider.description,
            auth_type=provider.auth_type,
            enabled=enabled,
            configured=configured,
            validated=validated,
            health=("disabled" if not enabled else ("healthy" if validated else "attention")),
            updated_at=configuration.updated_at if configuration else None,
            last_tested_at=last_tested_at,
        )

    async def _set_status(
        self,
        organization_id: uuid.UUID,
        key: str,
        status: str,
        message: str,
        actor: User,
        checked_at: datetime | None,
    ) -> None:
        await PlatformService(self.session).set_configuration(
            organization_id,
            f"integration-status.{key}",
            ConfigurationUpdate(
                value={
                    "status": status,
                    "message": message[:240],
                    "checked_at": checked_at.isoformat() if checked_at else None,
                },
                category="integration-status",
                is_secret=False,
            ),
            actor,
        )

    @staticmethod
    def _provider(key: str) -> ProviderDefinition:
        provider = PROVIDER_MAP.get(key)
        if provider is None:
            raise NotFoundError("Integration provider not found")
        return provider

    @staticmethod
    def _enabled(flag: FeatureFlag | None) -> bool:
        return flag.enabled if flag is not None else False
