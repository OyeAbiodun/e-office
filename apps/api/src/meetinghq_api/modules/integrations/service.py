"""Tenant-safe provider configuration and connectivity service."""

import asyncio
import builtins
import imaplib
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, cast

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.core.network import validate_public_http_endpoint
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
    SmtpConfigurationResponse,
    SmtpConfigurationUpdate,
    SmtpPriority,
    SmtpState,
    SmtpTestEmailResponse,
)
from meetinghq_api.modules.notifications.service import EmailDeliveryError, MeetingEmailSender
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError, ValidationError


class IntegrationService:
    """Keep provider secrets out of Platform Management."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.vault = SecretVault(self.settings.jwt_secret)

    async def smtp_configuration(self, organization_id: uuid.UUID) -> SmtpConfigurationResponse:
        """Return a safe, editable SMTP projection without the stored secret."""
        configuration = await self._configuration(organization_id, "smtp")
        status_entry = await self._status(organization_id, "smtp")
        if configuration is None or not configuration.value:
            return SmtpConfigurationResponse(
                provider_display_name="SMTP",
                host="",
                port=587,
                security_mode="starttls",
                allow_insecure=False,
                connection_timeout=self.settings.smtp_timeout_seconds,
                authentication_enabled=True,
                authentication_method="password",
                username=None,
                password_configured=False,
                password_mask=None,
                from_email=self.settings.smtp_from_email,
                from_name="MeetingHQ",
                reply_to=None,
                return_path=None,
                enabled=False,
                max_retry_attempts=self.settings.smtp_max_attempts,
                retry_delay_seconds=self.settings.smtp_retry_base_seconds,
                timeout_seconds=self.settings.smtp_timeout_seconds,
                default_priority="normal",
                state="not_configured",
                revision=0,
                updated_at=None,
                last_validated_at=None,
            )
        values = self.vault.open(dict(configuration.value))
        state, last_validated_at = self._smtp_state(values, status_entry)
        return SmtpConfigurationResponse(
            provider_display_name=str(values.get("provider_display_name") or "SMTP"),
            host=str(values.get("host") or ""),
            port=self._port(values.get("port"), 587),
            security_mode=self._smtp_security(values),
            allow_insecure=bool(values.get("allow_insecure", False)),
            connection_timeout=self._int_value(values.get("connection_timeout"), 20),
            authentication_enabled=bool(values.get("authentication_enabled", True)),
            authentication_method=str(values.get("authentication_method") or "password"),
            username=str(values["username"]) if values.get("username") else None,
            password_configured=bool(values.get("password")),
            password_mask="••••••••••••" if values.get("password") else None,
            from_email=str(values.get("from_email") or self.settings.smtp_from_email),
            from_name=str(values.get("from_name") or "MeetingHQ"),
            reply_to=str(values["reply_to"]) if values.get("reply_to") else None,
            return_path=str(values["return_path"]) if values.get("return_path") else None,
            enabled=bool(values.get("enabled", True)),
            max_retry_attempts=self._int_value(values.get("max_retry_attempts"), 3),
            retry_delay_seconds=self._float_value(values.get("retry_delay_seconds"), 0),
            timeout_seconds=self._int_value(values.get("timeout_seconds"), 20),
            default_priority=self._smtp_priority(values),
            state=state,
            revision=self._int_value(values.get("revision"), 1),
            updated_at=configuration.updated_at,
            last_validated_at=last_validated_at,
        )

    async def configure_smtp(
        self,
        organization_id: uuid.UUID,
        body: SmtpConfigurationUpdate,
        actor: User,
    ) -> SmtpConfigurationResponse:
        existing = await self._configuration(organization_id, "smtp")
        previous = self.vault.open(dict(existing.value)) if existing and existing.value else {}
        values = body.model_dump(mode="json")
        password = (body.password or "").strip()
        if password:
            values["password"] = password
        elif previous.get("password"):
            values["password"] = previous["password"]
        elif body.authentication_enabled:
            raise ValidationError("SMTP password is required when authentication is enabled")
        else:
            values.pop("password", None)
        values["revision"] = self._int_value(previous.get("revision"), 0) + 1
        await PlatformService(self.session).set_configuration(
            organization_id,
            "integration.smtp",
            ConfigurationUpdate(
                value=self.vault.seal(values), category="integrations", is_secret=True
            ),
            actor,
        )
        await self._set_status(
            organization_id,
            "smtp",
            "configured",
            "SMTP configuration is saved and requires validation.",
            actor,
            checked_at=None,
        )
        action = "smtp.configuration_updated" if existing else "smtp.configuration_created"
        self._audit(
            organization_id,
            actor.id,
            action,
            "smtp",
            {"status": "configured", "revision": values["revision"]},
        )
        if password and previous.get("password"):
            self._audit(
                organization_id,
                actor.id,
                "smtp.secret_rotated",
                "smtp",
                {"status": "recorded", "revision": values["revision"]},
            )
        if previous and bool(previous.get("enabled", True)) != body.enabled:
            self._audit(
                organization_id,
                actor.id,
                "smtp.enabled" if body.enabled else "smtp.disabled",
                "smtp",
                {"status": "recorded", "revision": values["revision"]},
            )
        await self.session.flush()
        return await self.smtp_configuration(organization_id)

    async def send_smtp_test_email(
        self, organization_id: uuid.UUID, recipient: str, actor: User
    ) -> SmtpTestEmailResponse:
        configuration = await self._configuration(organization_id, "smtp")
        if configuration is None or not configuration.value:
            raise NotFoundError("Configure SMTP before sending a test email")
        values = self.vault.open(dict(configuration.value))
        sender = MeetingEmailSender(self.settings, values)
        started = time.perf_counter()
        revision = self._int_value(values.get("revision"), 1)
        self._audit(
            organization_id,
            actor.id,
            "smtp.test_email_requested",
            "smtp",
            {"status": "requested", "recipient": recipient, "revision": revision},
        )
        try:
            message_id = await sender.send(
                recipient,
                "MeetingHQ SMTP delivery test",
                "MeetingHQ submitted this message through the configured outbound email path. "
                "SMTP acceptance does not by itself prove final mailbox delivery.",
            )
        except EmailDeliveryError as error:
            latency = max(1, round((time.perf_counter() - started) * 1000))
            diagnostic = self._safe_smtp_error(error)
            failed_at = datetime.now(UTC)
            await self._set_status(
                organization_id,
                "smtp",
                "failed",
                diagnostic,
                actor,
                checked_at=failed_at,
            )
            self._audit(
                organization_id,
                actor.id,
                "smtp.test_email_failed",
                "smtp",
                {
                    "status": "failed",
                    "latency_ms": latency,
                    "diagnostic": diagnostic,
                    "recipient": recipient,
                    "revision": revision,
                },
            )
            return SmtpTestEmailResponse(
                status="failed",
                message=diagnostic,
                recipient=recipient,
                message_id=None,
                latency_ms=latency,
                accepted_at=None,
            )
        accepted_at = datetime.now(UTC)
        latency = max(1, round((time.perf_counter() - started) * 1000))
        await self._set_status(
            organization_id,
            "smtp",
            "healthy",
            "SMTP provider accepted the latest test message.",
            actor,
            checked_at=accepted_at,
        )
        self._audit(
            organization_id,
            actor.id,
            "smtp.test_email_accepted",
            "smtp",
            {
                "status": "accepted",
                "latency_ms": latency,
                "recipient": recipient,
                "revision": revision,
            },
        )
        return SmtpTestEmailResponse(
            status="accepted",
            message=(
                "SMTP server accepted the test message; verify final delivery "
                "in the recipient mailbox."
            ),
            recipient=recipient,
            message_id=message_id,
            latency_ms=latency,
            accepted_at=accepted_at,
        )

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
            message = (
                self._safe_smtp_error(error)
                if key == "smtp"
                else f"Connection failed ({type(error).__name__}). Verify the provider settings."
            )
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
            "healthy" if response.status == "healthy" else "failed",
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
                "diagnostic": response.message,
                "revision": self._int_value(values.get("revision"), 1),
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
            await MeetingEmailSender(self.settings, values).test_connection()
            return "SMTP connection, TLS negotiation, authentication, and NOOP succeeded."
        if provider.auth_type == "imap":
            await asyncio.to_thread(self._probe_imap, values)
            return "IMAP authentication completed successfully."
        endpoint = self._endpoint(provider, values)
        await validate_public_http_endpoint(endpoint)
        headers: dict[str, str] = {}
        token = values.get("token") or values.get("api_key")
        if isinstance(token, str) and token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(endpoint, headers=headers)
            if response.is_redirect:
                raise ValueError("Provider endpoint redirects are not allowed during validation")
            response.raise_for_status()
        return f"{provider.name} endpoint responded with HTTP {response.status_code}."

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

    async def _configuration(
        self, organization_id: uuid.UUID, key: str
    ) -> ConfigurationEntry | None:
        return cast(
            ConfigurationEntry | None,
            await self.session.scalar(
                select(ConfigurationEntry).where(
                    ConfigurationEntry.organization_id == organization_id,
                    ConfigurationEntry.key == f"integration.{key}",
                )
            ),
        )

    async def _status(self, organization_id: uuid.UUID, key: str) -> ConfigurationEntry | None:
        return cast(
            ConfigurationEntry | None,
            await self.session.scalar(
                select(ConfigurationEntry).where(
                    ConfigurationEntry.organization_id == organization_id,
                    ConfigurationEntry.key == f"integration-status.{key}",
                )
            ),
        )

    @staticmethod
    def _smtp_security(values: dict[str, object]) -> Literal["starttls", "ssl_tls", "none"]:
        mode = values.get("security_mode")
        if mode in {"starttls", "ssl_tls", "none"}:
            return cast(Literal["starttls", "ssl_tls", "none"], mode)
        return "starttls" if values.get("starttls", True) else "none"

    @staticmethod
    def _smtp_priority(values: dict[str, object]) -> SmtpPriority:
        priority = values.get("default_priority")
        return cast(SmtpPriority, priority) if priority in {"low", "normal", "high"} else "normal"

    @staticmethod
    def _int_value(value: object, default: int) -> int:
        return int(value) if isinstance(value, (int, float, str)) else default

    @staticmethod
    def _float_value(value: object, default: float) -> float:
        return float(value) if isinstance(value, (int, float, str)) else default

    @staticmethod
    def _smtp_state(
        values: dict[str, object], status_entry: ConfigurationEntry | None
    ) -> tuple[SmtpState, datetime | None]:
        if not bool(values.get("enabled", True)):
            return "disabled", None
        status_value = status_entry.value if status_entry is not None else {}
        status = status_value.get("status") if isinstance(status_value, dict) else None
        checked = status_value.get("checked_at") if isinstance(status_value, dict) else None
        try:
            checked_at = datetime.fromisoformat(str(checked)) if checked else None
        except ValueError:
            checked_at = None
        mapped: dict[object, SmtpState] = {
            "configured": "configured",
            "testing": "testing",
            "healthy": "healthy",
            "attention": "degraded",
            "degraded": "degraded",
            "failed": "failed",
            "disabled": "disabled",
        }
        return mapped.get(status, "configured"), checked_at

    @staticmethod
    def _safe_smtp_error(error: Exception) -> str:
        name = type(error).__name__.lower()
        text = str(error).lower()
        if "authentication" in text or "auth" in name:
            return "SMTP authentication failed. Verify the username and app password."
        if "timeout" in text or "timeout" in name:
            return "SMTP connection timed out. Verify the host, port, and firewall rules."
        if "ssl" in name or "tls" in text or "certificate" in text:
            return "SMTP TLS negotiation failed. Verify the security mode and certificate."
        if "recipient" in text or "recipients" in name:
            return "SMTP rejected the recipient address."
        if "gaierror" in name or "name or service" in text:
            return "Unable to resolve the SMTP server hostname."
        if "connectionrefused" in name or "connect" in text:
            return "Unable to connect to the SMTP server. Verify the host and port."
        return "SMTP validation failed. Verify the provider settings."

    @staticmethod
    def _provider(key: str) -> ProviderDefinition:
        provider = PROVIDER_MAP.get(key)
        if provider is None:
            raise NotFoundError("Integration provider not found")
        return provider

    @staticmethod
    def _enabled(flag: FeatureFlag | None) -> bool:
        return flag.enabled if flag is not None else False
