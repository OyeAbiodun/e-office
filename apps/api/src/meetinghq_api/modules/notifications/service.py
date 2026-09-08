"""Meeting invitation delivery and reminder orchestration."""

import asyncio
import importlib
import json
import smtplib
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.core.secrets import SecretVault
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.configuration.models import ConfigurationEntry
from meetinghq_api.modules.meetings.models import Meeting, MeetingAttendee
from meetinghq_api.modules.notifications.email_templates import (
    EmailBranding,
    EmailTemplateRegistry,
    MeetingEmailData,
    RenderedEmail,
)
from meetinghq_api.modules.notifications.models import (
    BrowserPushDelivery,
    MeetingInvitationDelivery,
    MeetingReminder,
    Notification,
    NotificationPreference,
    PushSubscription,
)
from meetinghq_api.modules.notifications.schemas import (
    NotificationPreferenceUpdate,
    PushSubscriptionInput,
)
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import User
from meetinghq_api.shared.exceptions import NotFoundError, ValidationError
from meetinghq_api.shared.pagination import decode_cursor, encode_cursor

logger = structlog.get_logger(__name__)


class EmailDeliveryError(RuntimeError):
    """Safe outbound-delivery error that never includes provider secrets."""


class MeetingEmailSender:
    """SMTP delivery with a standards-compliant local outbox transport."""

    def __init__(
        self,
        settings: Settings,
        values: dict[str, object] | None = None,
        branding: EmailBranding | None = None,
    ) -> None:
        self.settings = settings
        self.values = values or {}
        self.branding = branding or EmailBranding()

    @classmethod
    async def for_organization(
        cls,
        session: AsyncSession,
        settings: Settings,
        organization_id: uuid.UUID | None,
    ) -> "MeetingEmailSender":
        """Resolve the tenant SMTP provider, falling back to environment transport."""
        if organization_id is None:
            return cls(settings)
        organization = await session.get(Organization, organization_id)
        branding = EmailBranding.from_organization(organization)
        entry = await session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.organization_id == organization_id,
                ConfigurationEntry.key == "integration.smtp",
            )
        )
        if entry is None:
            return cls(settings, branding=branding)
        return cls(
            settings,
            SecretVault(settings.jwt_secret).open(dict(entry.value)),
            branding=branding,
        )

    async def send(
        self,
        recipient: str,
        subject: str,
        text: str,
        ics: str | None = None,
        message_key: str | None = None,
        html: str | None = None,
        template_key: str | None = None,
        template_version: str | None = None,
    ) -> str:
        message = EmailMessage()
        from_email = self._string("from_email") or self.settings.smtp_from_email
        from_name = self._string("from_name")
        message["From"] = formataddr((from_name, from_email)) if from_name else from_email
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = format_datetime(datetime.now(UTC))
        if reply_to := self._string("reply_to"):
            message["Reply-To"] = reply_to
        if return_path := self._string("return_path"):
            message["Return-Path"] = return_path
        if priority := self._string("default_priority"):
            message["X-Priority"] = {"high": "1", "normal": "3", "low": "5"}.get(
                priority.lower(), "3"
            )
        message_id = f"<{message_key or uuid.uuid4()}@meetinghq>"
        message["Message-ID"] = message_id
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")
        if template_key:
            message["X-MeetingHQ-Template"] = template_key
        if template_version:
            message["X-MeetingHQ-Template-Version"] = template_version
        if ics:
            method = "CANCEL" if "\r\nMETHOD:CANCEL\r\n" in ics else "REQUEST"
            message.add_attachment(
                ics.encode(),
                maintype="text",
                subtype="calendar",
                filename="meeting.ics",
                params={"method": method},
            )
        await self.send_message(message)
        return message_id

    async def send_rendered(
        self,
        recipient: str,
        rendered: RenderedEmail,
        ics: str | None = None,
        message_key: str | None = None,
    ) -> str:
        """Send a registry-rendered email through the existing hardened transport."""
        await logger.ainfo(
            "transactional_email_rendered",
            template_key=rendered.key,
            template_version=rendered.version,
            recipient_domain=recipient.rpartition("@")[2].lower(),
        )
        try:
            return await self.send(
                recipient,
                rendered.subject,
                rendered.text,
                ics,
                message_key,
                html=rendered.html,
                template_key=rendered.key,
                template_version=rendered.version,
            )
        except TypeError as error:
            # Existing in-process delivery adapters may implement the original
            # positional contract. Keep that test/delivery seam compatible while
            # production sends always receive the multipart representation above.
            if "unexpected keyword argument" not in str(error):
                raise
            return await self.send(recipient, rendered.subject, rendered.text, ics, message_key)

    async def send_message(self, message: EmailMessage) -> None:
        """Send a prepared message through the same application-wide transport."""
        if self._smtp_host():
            if not self._enabled():
                raise EmailDeliveryError("Outbound SMTP delivery is disabled")
            await self._send_with_retry(message)
            return
        await asyncio.to_thread(self._write_outbox, message)

    async def test_connection(self) -> None:
        """Validate the configured SMTP handshake without sending a message."""
        if not self._smtp_host():
            raise EmailDeliveryError("SMTP is not configured")
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._smtp_connect),
                timeout=self._timeout() + 2,
            )
        except EmailDeliveryError:
            raise
        except Exception as exc:
            raise EmailDeliveryError(
                f"SMTP connection validation failed ({type(exc).__name__})"
            ) from exc

    @property
    def configured(self) -> bool:
        """Return whether this resolved tenant transport has an SMTP endpoint."""
        return bool(self._smtp_host())

    @property
    def enabled(self) -> bool:
        """Return whether configured outbound delivery is enabled."""
        return self._enabled()

    @property
    def delivery_mode(self) -> Literal["smtp", "local_outbox"]:
        """Identify whether a send reaches an SMTP provider or only local storage.

        A local outbox is useful for development inspection, but it is not an
        externally delivered message. Callers use this distinction in user-visible
        and audit outcomes rather than presenting a local file write as SMTP
        acceptance.
        """
        return "smtp" if self.configured else "local_outbox"

    async def _send_with_retry(self, message: EmailMessage) -> None:
        max_attempts = self._max_attempts()
        for attempt in range(1, max_attempts + 1):
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._smtp_send, message),
                    timeout=self._timeout() + 2,
                )
                return
            except smtplib.SMTPAuthenticationError as exc:
                raise EmailDeliveryError("SMTP authentication failed") from exc
            except smtplib.SMTPRecipientsRefused as exc:
                raise EmailDeliveryError("SMTP rejected one or more recipients") from exc
            except Exception as exc:
                await logger.awarning(
                    "smtp_delivery_attempt_failed",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error_type=type(exc).__name__,
                )
                if attempt >= max_attempts:
                    raise EmailDeliveryError(
                        f"SMTP delivery failed ({type(exc).__name__})"
                    ) from exc
                await asyncio.sleep(self._retry_base_seconds() * (2 ** (attempt - 1)))

    def _write_outbox(self, message: EmailMessage) -> None:
        outbox = Path(self.settings.email_outbox_path).resolve()
        outbox.mkdir(parents=True, exist_ok=True)
        (outbox / f"{uuid.uuid4()}.eml").write_bytes(message.as_bytes())

    def _smtp_send(self, message: EmailMessage) -> None:
        host = self._smtp_host()
        if host is None:
            raise RuntimeError("SMTP host is not configured")
        with self._client(host) as smtp:
            self._authenticate(smtp)
            smtp.send_message(message)

    def _smtp_connect(self) -> None:
        host = self._smtp_host()
        if host is None:
            raise EmailDeliveryError("SMTP is not configured")
        with self._client(host) as smtp:
            self._authenticate(smtp)
            smtp.noop()

    def _client(self, host: str) -> smtplib.SMTP:
        security = self._security_mode()
        context = ssl.create_default_context()
        if security == "ssl_tls":
            return smtplib.SMTP_SSL(host, self._port(), timeout=self._timeout(), context=context)
        client = smtplib.SMTP(host, self._port(), timeout=self._timeout())
        if security == "starttls":
            client.starttls(context=context)
        return client

    def _authenticate(self, smtp: smtplib.SMTP) -> None:
        authentication_enabled = self.values.get("authentication_enabled", True)
        if not bool(authentication_enabled):
            return
        username = self._string("username") or self.settings.smtp_username
        if username:
            smtp.login(username, self._string("password") or self.settings.smtp_password or "")

    def _smtp_host(self) -> str | None:
        return self._string("host") or self.settings.smtp_host

    def _port(self) -> int:
        value = self.values.get("port")
        return int(value) if isinstance(value, (int, str)) else self.settings.smtp_port

    def _starttls(self) -> bool:
        return self._security_mode() == "starttls"

    def _security_mode(self) -> str:
        value = self._string("security_mode")
        if value in {"starttls", "ssl_tls", "none"}:
            return value
        legacy = self.values.get("starttls")
        if isinstance(legacy, bool):
            return "starttls" if legacy else "none"
        return "starttls" if self.settings.smtp_starttls else "none"

    def _enabled(self) -> bool:
        value = self.values.get("enabled")
        return bool(value) if isinstance(value, bool) else True

    def _timeout(self) -> int:
        value = self.values.get("timeout_seconds") or self.values.get("connection_timeout")
        return int(value) if isinstance(value, (int, str)) else self.settings.smtp_timeout_seconds

    def _max_attempts(self) -> int:
        value = self.values.get("max_retry_attempts")
        return int(value) if isinstance(value, (int, str)) else self.settings.smtp_max_attempts

    def _retry_base_seconds(self) -> float:
        value = self.values.get("retry_delay_seconds")
        return (
            float(value)
            if isinstance(value, (int, float, str))
            else self.settings.smtp_retry_base_seconds
        )

    def _string(self, key: str) -> str | None:
        value = self.values.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None


class NotificationService:
    """Tenant-safe meeting notifications, invitation delivery, and reminders."""

    REMINDER_OFFSETS = (15, 30, 60, 1440)

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def _email(self, organization_id: uuid.UUID) -> MeetingEmailSender:
        return await MeetingEmailSender.for_organization(
            self.session, self.settings, organization_id
        )

    async def create_notification(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        action_url: str | None = None,
        meeting_id: uuid.UUID | None = None,
        category: str = "general",
        priority: str = "normal",
        metadata: dict[str, object] | None = None,
    ) -> Notification:
        """Persist an in-app notification and queue eligible device delivery.

        The browser push outbox is transactionally created with its in-app
        notification. A worker sends only committed rows, so an HTTP request
        never has to remain open while an external push provider is contacted.
        """
        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            meeting_id=meeting_id,
            notification_type=notification_type,
            category=category,
            priority=priority,
            title=title,
            body=body,
            action_url=action_url,
            notification_metadata=metadata or {},
        )
        self.session.add(notification)
        await self.session.flush()
        await self._enqueue_browser_push(notification)
        return notification

    async def list_for_user(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str | None = None,
        priority: str | None = None,
        unread_only: bool = False,
        include_archived: bool = False,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        cursor: str | None = None,
    ) -> tuple[list[Notification], int, int, str | None, dict[str, int]]:
        query = select(Notification).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
        )
        if not include_archived:
            query = query.where(Notification.archived_at.is_(None))
        if category:
            query = query.where(Notification.category == category)
        if priority:
            query = query.where(Notification.priority == priority)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        if search:
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Notification.title.ilike(pattern),
                    Notification.body.ilike(pattern),
                )
            )
        if cursor:
            try:
                cursor_at, cursor_id = decode_cursor(cursor)
                cursor_uuid = uuid.UUID(cursor_id)
            except (ValueError, TypeError) as exc:
                raise ValidationError("Invalid notification cursor") from exc
            query = query.where(
                or_(
                    Notification.delivered_at < cursor_at,
                    (Notification.delivered_at == cursor_at) & (Notification.id < cursor_uuid),
                )
            )
        count_query = select(func.count()).select_from(query.subquery())
        total = int(await self.session.scalar(count_query) or 0)
        if not cursor:
            query = query.offset((page - 1) * page_size)
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(
                        Notification.delivered_at.desc(),
                        Notification.id.desc(),
                    ).limit(page_size + 1)
                )
            ).all()
        )
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        next_cursor = (
            encode_cursor(rows[-1].delivered_at, str(rows[-1].id)) if has_more and rows else None
        )
        unread = (
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.organization_id == organization_id,
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                )
            )
            or 0
        )
        attention: dict[str, int] = {}
        for key in ("mentions", "meetings", "approvals", "tasks"):
            attention[key] = int(
                await self.session.scalar(
                    select(func.count(Notification.id)).where(
                        Notification.organization_id == organization_id,
                        Notification.user_id == user_id,
                        Notification.archived_at.is_(None),
                        Notification.read_at.is_(None),
                        Notification.category == key,
                    )
                )
                or 0
            )
        return rows, int(unread), total, next_cursor, attention

    async def bulk_action(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_ids: list[uuid.UUID],
        action: str,
    ) -> int:
        rows = list(
            (
                await self.session.scalars(
                    select(Notification).where(
                        Notification.organization_id == organization_id,
                        Notification.user_id == user_id,
                        Notification.id.in_(notification_ids),
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            if action == "read":
                row.read_at = now
            else:
                row.archived_at = now
        return len(rows)

    async def mark_read(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
        if item is None:
            raise NotFoundError("Notification not found")
        item.read_at = datetime.now(UTC)
        return item

    async def mark_all_read(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
        rows = (
            await self.session.scalars(
                select(Notification).where(
                    Notification.organization_id == organization_id,
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
        ).all()
        now = datetime.now(UTC)
        for row in rows:
            row.read_at = now
        return len(rows)

    async def archive(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self._owned_notification(organization_id, user_id, notification_id)
        item.archived_at = datetime.now(UTC)
        return item

    async def preferences(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationPreference:
        item = await self.session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.organization_id == organization_id,
                NotificationPreference.user_id == user_id,
            )
        )
        if item is None:
            item = NotificationPreference(
                organization_id=organization_id,
                user_id=user_id,
                in_app_enabled=True,
                email_enabled=True,
                browser_enabled=False,
                quiet_hours_enabled=False,
                timezone="UTC",
                category_rules={},
                delivery_rules={},
            )
            self.session.add(item)
            await self.session.flush()
        return item

    async def update_preferences(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        item = await self.preferences(organization_id, user_id)
        for field, value in body.model_dump().items():
            setattr(item, field, value)
        item.updated_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="notifications.preferences_updated",
                resource="notification_preferences",
                resource_id=item.id,
                audit_metadata={},
            )
        )
        await self.session.flush()
        return item

    async def upsert_push_subscription(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: PushSubscriptionInput,
    ) -> PushSubscription:
        """Register or refresh one browser without exposing it to another tenant."""
        item = await self.session.scalar(
            select(PushSubscription).where(
                PushSubscription.organization_id == organization_id,
                PushSubscription.endpoint == body.endpoint,
            )
        )
        if item is None:
            item = PushSubscription(
                organization_id=organization_id,
                user_id=user_id,
                endpoint=body.endpoint,
                p256dh=body.p256dh,
                auth=body.auth,
                user_agent=body.user_agent,
                enabled=True,
                last_used_at=datetime.now(UTC),
            )
            self.session.add(item)
        else:
            # An endpoint can only ever belong to one user in this tenant. A
            # browser refresh may rotate keys, but cannot claim another user's
            # device subscription.
            if item.user_id != user_id:
                raise ValidationError("Push subscription is already registered")
            item.p256dh = body.p256dh
            item.auth = body.auth
            item.user_agent = body.user_agent
            item.enabled = True
            item.last_used_at = datetime.now(UTC)
        await self.session.flush()
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="notifications.push_subscription_upserted",
                resource="push_subscription",
                resource_id=item.id,
                audit_metadata={},
            )
        )
        return item

    async def list_push_subscriptions(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[PushSubscription]:
        return list(
            (
                await self.session.scalars(
                    select(PushSubscription)
                    .where(
                        PushSubscription.organization_id == organization_id,
                        PushSubscription.user_id == user_id,
                    )
                    .order_by(PushSubscription.last_used_at.desc().nullslast())
                )
            ).all()
        )

    async def revoke_push_subscription(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, subscription_id: uuid.UUID
    ) -> None:
        item = await self.session.scalar(
            select(PushSubscription).where(
                PushSubscription.id == subscription_id,
                PushSubscription.organization_id == organization_id,
                PushSubscription.user_id == user_id,
            )
        )
        if item is None:
            raise NotFoundError("Push subscription not found")
        item.enabled = False
        item.last_used_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="notifications.push_subscription_revoked",
                resource="push_subscription",
                resource_id=item.id,
                audit_metadata={},
            )
        )
        await self.session.flush()

    async def _enqueue_browser_push(self, notification: Notification) -> None:
        """Create a delivery row only for configured, opted-in browser devices."""
        if not self._web_push_configured():
            return
        preference = await self.session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.organization_id == notification.organization_id,
                NotificationPreference.user_id == notification.user_id,
            )
        )
        if preference is None or not self._browser_delivery_allowed(preference, notification):
            return
        subscriptions = list(
            (
                await self.session.scalars(
                    select(PushSubscription).where(
                        PushSubscription.organization_id == notification.organization_id,
                        PushSubscription.user_id == notification.user_id,
                        PushSubscription.enabled.is_(True),
                    )
                )
            ).all()
        )
        for subscription in subscriptions:
            self.session.add(
                BrowserPushDelivery(
                    organization_id=notification.organization_id,
                    notification_id=notification.id,
                    subscription_id=subscription.id,
                )
            )

    async def process_due_browser_pushes(self) -> int:
        """Deliver a bounded batch of committed Web Push outbox records."""
        if not self._web_push_configured():
            return 0
        now = datetime.now(UTC)
        deliveries = list(
            (
                await self.session.scalars(
                    select(BrowserPushDelivery)
                    .where(
                        or_(
                            BrowserPushDelivery.status == "pending",
                            (
                                (BrowserPushDelivery.status == "failed")
                                & (BrowserPushDelivery.next_attempt_at <= now)
                            ),
                        ),
                        BrowserPushDelivery.attempt_count < self.settings.delivery_max_attempts,
                    )
                    .order_by(BrowserPushDelivery.created_at)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        delivered = 0
        for delivery in deliveries:
            notification = await self.session.get(Notification, delivery.notification_id)
            subscription = await self.session.get(PushSubscription, delivery.subscription_id)
            if (
                notification is None
                or subscription is None
                or not subscription.enabled
                or notification.organization_id != delivery.organization_id
                or subscription.organization_id != delivery.organization_id
                or subscription.user_id != notification.user_id
            ):
                delivery.status = "cancelled"
                delivery.next_attempt_at = None
                continue
            preference = await self.session.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.organization_id == notification.organization_id,
                    NotificationPreference.user_id == notification.user_id,
                )
            )
            if preference is None or not self._browser_delivery_allowed(preference, notification):
                delivery.status = "cancelled"
                delivery.next_attempt_at = None
                continue
            delivery.attempt_count += 1
            delivery.last_attempt_at = now
            try:
                await asyncio.to_thread(self._send_web_push, subscription, notification)
                delivery.status = "sent"
                delivery.delivered_at = now
                delivery.error = None
                delivery.next_attempt_at = None
                subscription.last_used_at = now
                delivered += 1
            except Exception as exc:
                status_code = self._push_status_code(exc)
                if status_code in {404, 410}:
                    subscription.enabled = False
                    delivery.status = "cancelled"
                    delivery.next_attempt_at = None
                else:
                    delivery.status = "failed"
                    delivery.next_attempt_at = self._next_attempt_at(delivery.attempt_count, now)
                delivery.error = self._safe_push_error(exc)
                self.session.add(
                    AuditLog(
                        organization_id=delivery.organization_id,
                        user_id=notification.user_id,
                        action="notifications.browser_push_failed",
                        resource="browser_push_delivery",
                        resource_id=delivery.id,
                        audit_metadata={
                            "notification_type": notification.notification_type,
                            "status_code": status_code,
                            "attempt": delivery.attempt_count,
                        },
                    )
                )
        return delivered

    def _web_push_configured(self) -> bool:
        return bool(
            self.settings.web_push_vapid_private_key
            and self.settings.web_push_vapid_public_key
            and self.settings.web_push_vapid_subject
        )

    def _browser_delivery_allowed(
        self, preference: NotificationPreference, notification: Notification
    ) -> bool:
        if not preference.browser_enabled or self._in_quiet_hours(preference):
            return False
        category_rule = preference.category_rules.get(notification.category)
        if isinstance(category_rule, dict) and category_rule.get("browser") is False:
            return False
        return True

    @staticmethod
    def _in_quiet_hours(preference: NotificationPreference) -> bool:
        if (
            not preference.quiet_hours_enabled
            or not preference.quiet_hours_start
            or not preference.quiet_hours_end
        ):
            return False
        try:
            zone = ZoneInfo(preference.timezone)
            now = datetime.now(zone).time()
            start = datetime.strptime(preference.quiet_hours_start, "%H:%M").time()
            end = datetime.strptime(preference.quiet_hours_end, "%H:%M").time()
        except (ValueError, ZoneInfoNotFoundError):
            return False
        return start <= now < end if start <= end else now >= start or now < end

    def _send_web_push(self, subscription: PushSubscription, notification: Notification) -> None:
        """Call the standards-based provider without recording endpoint details."""
        try:
            provider: Any = importlib.import_module("pywebpush")
        except ModuleNotFoundError as exc:
            raise RuntimeError("Web Push delivery provider is unavailable") from exc
        payload = json.dumps(
            {
                "title": notification.title,
                "body": notification.body,
                "url": notification.action_url or "/notifications",
                "tag": f"notification-{notification.id}",
                "data": {"notification_id": str(notification.id)},
            }
        )
        provider.webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload,
            vapid_private_key=self.settings.web_push_vapid_private_key,
            vapid_claims={"sub": self.settings.web_push_vapid_subject},
        )

    @staticmethod
    def _push_status_code(error: Exception) -> int | None:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        return status_code if isinstance(status_code, int) else None

    @staticmethod
    def _safe_push_error(error: Exception) -> str:
        status_code = NotificationService._push_status_code(error)
        if status_code is not None:
            return f"Web Push provider returned HTTP {status_code}"
        return f"Web Push delivery failed ({type(error).__name__})"

    async def _owned_notification(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
        if item is None:
            raise NotFoundError("Notification not found")
        return item

    async def invite_participants(
        self, meeting: Meeting, organizer: User, participant_ids: set[uuid.UUID]
    ) -> None:
        if not participant_ids:
            return
        participants = list(
            (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == meeting.organization_id,
                        User.id.in_(participant_ids),
                    )
                )
            ).all()
        )
        ics = self.ics(meeting, organizer, participants)
        email = await self._email(meeting.organization_id)
        for participant in participants:
            await self.create_notification(
                organization_id=meeting.organization_id,
                user_id=participant.id,
                meeting_id=meeting.id,
                notification_type="meeting_invitation",
                title=f"Meeting invitation: {meeting.title}",
                body=self._invitation_text(meeting, organizer),
                action_url=f"/meetings/{meeting.id}",
                category="meetings",
            )
            in_app = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="in_app",
                recipient=str(participant.id),
                status="sent",
                sent_at=datetime.now(UTC),
            )
            email_delivery = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="email",
                recipient=participant.email,
            )
            ics_delivery = MeetingInvitationDelivery(
                organization_id=meeting.organization_id,
                meeting_id=meeting.id,
                user_id=participant.id,
                channel="ics",
                recipient=participant.email,
            )
            self.session.add_all([in_app, email_delivery, ics_delivery])
            await self.session.flush()
            attempted_at = datetime.now(UTC)
            try:
                rendered = self._meeting_email("meeting.invitation", meeting, organizer, email)
                transport_id = await email.send_rendered(
                    participant.email,
                    rendered,
                    ics=ics,
                    message_key=f"meeting-{email_delivery.id}",
                )
                for delivery in (email_delivery, ics_delivery):
                    delivery.status = "sent"
                    delivery.transport_id = transport_id
                    delivery.sent_at = attempted_at
                    delivery.attempt_count = 1
                    delivery.last_attempt_at = attempted_at
                await self._record_delivery_audit(
                    meeting,
                    organizer.id,
                    "meeting.delivery.accepted",
                    "meeting_invitation",
                    ["email", "ics"],
                    participant.email,
                    transport_id,
                    rendered,
                )
            except Exception as exc:
                for delivery in (email_delivery, ics_delivery):
                    delivery.status = "failed"
                    delivery.error = self._safe_delivery_error(exc)
                    delivery.attempt_count = 1
                    delivery.last_attempt_at = attempted_at
                    delivery.next_attempt_at = self._next_attempt_at(1, attempted_at)
                self.session.add(
                    AuditLog(
                        organization_id=meeting.organization_id,
                        user_id=organizer.id,
                        action="meeting.delivery.failed",
                        resource="meeting",
                        resource_id=meeting.id,
                        audit_metadata={
                            "notification_type": "meeting_invitation",
                            "channels": ["email", "ics"],
                            "error": self._safe_delivery_error(exc),
                        },
                    )
                )
            for offset in self.REMINDER_OFFSETS:
                scheduled_for = meeting.start_datetime - timedelta(minutes=offset)
                if scheduled_for > datetime.now(UTC):
                    self.session.add(
                        MeetingReminder(
                            organization_id=meeting.organization_id,
                            meeting_id=meeting.id,
                            user_id=participant.id,
                            offset_minutes=offset,
                            scheduled_for=scheduled_for,
                        )
                    )

    async def schedule_reminders(self, meeting: Meeting, user_ids: set[uuid.UUID]) -> None:
        now = datetime.now(UTC)
        for user_id in user_ids:
            for offset in self.REMINDER_OFFSETS:
                scheduled_for = meeting.start_datetime - timedelta(minutes=offset)
                if scheduled_for > now:
                    self.session.add(
                        MeetingReminder(
                            organization_id=meeting.organization_id,
                            meeting_id=meeting.id,
                            user_id=user_id,
                            offset_minutes=offset,
                            scheduled_for=scheduled_for,
                        )
                    )

    async def notify_organizer(
        self,
        meeting: Meeting,
        notification_type: str,
        title: str,
        body: str,
    ) -> None:
        await self.create_notification(
            organization_id=meeting.organization_id,
            user_id=meeting.organizer_id,
            meeting_id=meeting.id,
            notification_type=notification_type,
            title=title,
            body=body,
            action_url=f"/meetings/{meeting.id}",
            category="meetings",
        )

    async def notify_participants(
        self,
        meeting: Meeting,
        notification_type: str,
        subject: str,
        body: str,
        include_organizer: bool = False,
        calendar_method: str | None = None,
        previous_start_time: datetime | None = None,
        previous_end_time: datetime | None = None,
    ) -> None:
        attendee_ids = set(
            (
                await self.session.scalars(
                    select(MeetingAttendee.user_id).where(MeetingAttendee.meeting_id == meeting.id)
                )
            ).all()
        )
        if not include_organizer:
            attendee_ids.discard(meeting.organizer_id)
        users = list(
            (
                await self.session.scalars(
                    select(User).where(
                        User.organization_id == meeting.organization_id,
                        User.id.in_(attendee_ids),
                    )
                )
            ).all()
        )
        email = await self._email(meeting.organization_id)
        organizer = await self.session.get(User, meeting.organizer_id)
        if organizer is None:
            raise NotFoundError("Meeting organizer not found")
        ics = (
            self.ics(
                meeting,
                organizer,
                users,
                method=calendar_method,
                status="CANCELLED" if calendar_method == "CANCEL" else "CONFIRMED",
            )
            if calendar_method
            else None
        )
        channel_suffix = (
            "cancel"
            if calendar_method == "CANCEL"
            else "update" if calendar_method == "REQUEST" else None
        )
        for user in users:
            await self.create_notification(
                organization_id=meeting.organization_id,
                user_id=user.id,
                meeting_id=meeting.id,
                notification_type=notification_type,
                title=subject,
                body=body,
                action_url=f"/meetings/{meeting.id}",
                category="meetings",
            )
            deliveries: list[MeetingInvitationDelivery] = []
            if channel_suffix:
                for prefix in ("email", "ics"):
                    channel = f"{prefix}_{channel_suffix}"
                    delivery = await self.session.scalar(
                        select(MeetingInvitationDelivery).where(
                            MeetingInvitationDelivery.meeting_id == meeting.id,
                            MeetingInvitationDelivery.user_id == user.id,
                            MeetingInvitationDelivery.channel == channel,
                        )
                    )
                    if delivery is None:
                        delivery = MeetingInvitationDelivery(
                            organization_id=meeting.organization_id,
                            meeting_id=meeting.id,
                            user_id=user.id,
                            channel=channel,
                            recipient=user.email,
                            attempt_count=0,
                        )
                        self.session.add(delivery)
                    deliveries.append(delivery)
            if deliveries:
                await self.session.flush()
            attempted_at = datetime.now(UTC)
            try:
                primary_delivery = next(
                    (item for item in deliveries if item.channel.startswith("email")), None
                )
                template_key: Literal[
                    "meeting.updated", "meeting.cancelled", "meeting.invitation"
                ] = (
                    "meeting.cancelled"
                    if notification_type == "meeting_cancelled"
                    else (
                        "meeting.updated"
                        if notification_type == "meeting_updated"
                        else "meeting.invitation"
                    )
                )
                rendered = self._meeting_email(
                    template_key,
                    meeting,
                    organizer,
                    email,
                    previous_start_time=previous_start_time,
                    previous_end_time=previous_end_time,
                )
                transport_id = await email.send_rendered(
                    user.email,
                    rendered,
                    ics=ics,
                    message_key=(
                        f"meeting-{primary_delivery.id}" if primary_delivery is not None else None
                    ),
                )
                for delivery in deliveries:
                    delivery.status = "sent"
                    delivery.transport_id = transport_id
                    delivery.error = None
                    delivery.attempt_count += 1
                    delivery.last_attempt_at = attempted_at
                    delivery.next_attempt_at = None
                    delivery.sent_at = attempted_at
                await self._record_delivery_audit(
                    meeting,
                    meeting.organizer_id,
                    "meeting.delivery.accepted",
                    notification_type,
                    [item.channel for item in deliveries],
                    user.email,
                    transport_id,
                    rendered,
                )
            except Exception as exc:
                for delivery in deliveries:
                    delivery.status = "failed"
                    delivery.error = self._safe_delivery_error(exc)
                    delivery.attempt_count += 1
                    delivery.last_attempt_at = attempted_at
                    delivery.next_attempt_at = self._next_attempt_at(
                        delivery.attempt_count, attempted_at
                    )
                self.session.add(
                    AuditLog(
                        organization_id=meeting.organization_id,
                        user_id=meeting.organizer_id,
                        action="meeting.delivery.failed",
                        resource="meeting",
                        resource_id=meeting.id,
                        audit_metadata={
                            "notification_type": notification_type,
                            "channels": [item.channel for item in deliveries],
                            "error": self._safe_delivery_error(exc),
                        },
                    )
                )

    async def process_due_invitations(self) -> int:
        """Retry durable invitation deliveries without blocking meeting creation."""
        now = datetime.now(UTC)
        deliveries = list(
            (
                await self.session.scalars(
                    select(MeetingInvitationDelivery)
                    .where(
                        MeetingInvitationDelivery.channel.like("email%"),
                        MeetingInvitationDelivery.status == "failed",
                        MeetingInvitationDelivery.next_attempt_at <= now,
                        MeetingInvitationDelivery.attempt_count
                        < self.settings.delivery_max_attempts,
                    )
                    .order_by(MeetingInvitationDelivery.next_attempt_at)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        delivered = 0
        senders: dict[uuid.UUID, MeetingEmailSender] = {}
        for delivery in deliveries:
            meeting = await self.session.get(Meeting, delivery.meeting_id)
            user = await self.session.get(User, delivery.user_id)
            organizer = (
                await self.session.get(User, meeting.organizer_id) if meeting is not None else None
            )
            companion_channel = delivery.channel.replace("email", "ics", 1)
            companions = list(
                (
                    await self.session.scalars(
                        select(MeetingInvitationDelivery).where(
                            MeetingInvitationDelivery.organization_id == delivery.organization_id,
                            MeetingInvitationDelivery.meeting_id == delivery.meeting_id,
                            MeetingInvitationDelivery.user_id == delivery.user_id,
                            MeetingInvitationDelivery.channel.in_(
                                (delivery.channel, companion_channel)
                            ),
                        )
                    )
                ).all()
            )
            if (
                meeting is None
                or user is None
                or organizer is None
                or (meeting.status.value == "cancelled" and not delivery.channel.endswith("cancel"))
            ):
                for item in companions:
                    item.status = "cancelled"
                    item.next_attempt_at = None
                continue
            attempted_at = datetime.now(UTC)
            attempt = delivery.attempt_count + 1
            try:
                sender = senders.get(meeting.organization_id)
                if sender is None:
                    sender = await self._email(meeting.organization_id)
                    senders[meeting.organization_id] = sender
                method = "CANCEL" if delivery.channel.endswith("cancel") else "REQUEST"
                template_key: Literal[
                    "meeting.invitation", "meeting.updated", "meeting.cancelled"
                ] = (
                    "meeting.cancelled"
                    if delivery.channel.endswith("cancel")
                    else (
                        "meeting.updated"
                        if delivery.channel.endswith("update")
                        else "meeting.invitation"
                    )
                )
                rendered = self._meeting_email(template_key, meeting, organizer, sender)
                transport_id = await sender.send_rendered(
                    user.email,
                    rendered,
                    ics=self.ics(
                        meeting,
                        organizer,
                        [user],
                        method=method,
                        status="CANCELLED" if method == "CANCEL" else "CONFIRMED",
                    ),
                    message_key=f"meeting-{delivery.id}",
                )
                for item in companions:
                    item.status = "sent"
                    item.transport_id = transport_id
                    item.sent_at = attempted_at
                    item.error = None
                    item.attempt_count = attempt
                    item.last_attempt_at = attempted_at
                    item.next_attempt_at = None
                await self._record_delivery_audit(
                    meeting,
                    organizer.id,
                    "meeting.delivery.retry_accepted",
                    self._retry_notification_type(delivery.channel),
                    [item.channel for item in companions],
                    user.email,
                    transport_id,
                    rendered,
                )
                delivered += 1
            except Exception as exc:
                for item in companions:
                    item.status = "failed"
                    item.error = self._safe_delivery_error(exc)
                    item.attempt_count = attempt
                    item.last_attempt_at = attempted_at
                    item.next_attempt_at = self._next_attempt_at(attempt, attempted_at)
        return delivered

    async def process_due_reminders(self) -> int:
        now = datetime.now(UTC)
        reminders = list(
            (
                await self.session.scalars(
                    select(MeetingReminder)
                    .where(
                        or_(
                            (
                                (MeetingReminder.status == "pending")
                                & (MeetingReminder.scheduled_for <= now)
                            ),
                            (
                                (MeetingReminder.status == "failed")
                                & (MeetingReminder.next_attempt_at <= now)
                            ),
                        ),
                        MeetingReminder.attempt_count < self.settings.delivery_max_attempts,
                    )
                    .order_by(MeetingReminder.scheduled_for)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        delivered = 0
        senders: dict[uuid.UUID, MeetingEmailSender] = {}
        for reminder in reminders:
            meeting = await self.session.get(Meeting, reminder.meeting_id)
            user = await self.session.get(User, reminder.user_id)
            if meeting is None or user is None or meeting.status.value == "cancelled":
                reminder.status = "cancelled"
                continue
            reminder.status = "processing"
            reminder.attempt_count += 1
            reminder.last_attempt_at = datetime.now(UTC)
            body = (
                f"{meeting.title} starts in {self._offset_label(reminder.offset_minutes)} "
                f"at {meeting.start_datetime.isoformat()} ({meeting.timezone})."
            )
            try:
                sender = senders.get(meeting.organization_id)
                if sender is None:
                    sender = await self._email(meeting.organization_id)
                    senders[meeting.organization_id] = sender
                organizer = await self.session.get(User, meeting.organizer_id)
                if organizer is None:
                    raise NotFoundError("Meeting organizer not found")
                rendered = self._meeting_email(
                    "meeting.reminder",
                    meeting,
                    organizer,
                    sender,
                    reminder_label=self._offset_label(reminder.offset_minutes),
                )
                await sender.send_rendered(user.email, rendered)
                await self.create_notification(
                    organization_id=meeting.organization_id,
                    user_id=user.id,
                    meeting_id=meeting.id,
                    notification_type="meeting_reminder",
                    title=f"Upcoming: {meeting.title}",
                    body=body,
                    action_url=f"/meetings/{meeting.id}",
                    category="meetings",
                )
                reminder.status = "sent"
                reminder.delivered_at = datetime.now(UTC)
                reminder.error = None
                reminder.next_attempt_at = None
                await self._record_delivery_audit(
                    meeting,
                    meeting.organizer_id,
                    "meeting.reminder.accepted",
                    "meeting_reminder",
                    ["email", "in_app"],
                    user.email,
                    None,
                    rendered,
                )
                delivered += 1
            except Exception as exc:
                reminder.status = "failed"
                reminder.error = self._safe_delivery_error(exc)
                reminder.next_attempt_at = self._next_attempt_at(
                    reminder.attempt_count, reminder.last_attempt_at
                )
                self.session.add(
                    AuditLog(
                        organization_id=meeting.organization_id,
                        user_id=meeting.organizer_id,
                        action="meeting.reminder.failed",
                        resource="meeting",
                        resource_id=meeting.id,
                        audit_metadata={
                            "notification_type": "meeting_reminder",
                            "recipient_domain": self._recipient_domain(user.email),
                            "error": self._safe_delivery_error(exc),
                            "attempt": reminder.attempt_count,
                        },
                    )
                )
        return delivered

    async def _record_delivery_audit(
        self,
        meeting: Meeting,
        actor_id: uuid.UUID,
        action: str,
        notification_type: str,
        channels: list[str],
        recipient: str,
        transport_id: str | None,
        rendered: RenderedEmail | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=meeting.organization_id,
                user_id=actor_id,
                action=action,
                resource="meeting",
                resource_id=meeting.id,
                audit_metadata={
                    "notification_type": notification_type,
                    "channels": channels,
                    "recipient_domain": self._recipient_domain(recipient),
                    "transport_id": transport_id,
                    "template_key": rendered.key if rendered else None,
                    "template_version": rendered.version if rendered else None,
                },
            )
        )
        await self.session.flush()

    @staticmethod
    def _recipient_domain(recipient: str) -> str:
        return recipient.rpartition("@")[2].lower()

    def _meeting_email(
        self,
        template_key: Literal[
            "meeting.invitation", "meeting.updated", "meeting.cancelled", "meeting.reminder"
        ],
        meeting: Meeting,
        organizer: User,
        sender: MeetingEmailSender,
        *,
        previous_start_time: datetime | None = None,
        previous_end_time: datetime | None = None,
        reminder_label: str | None = None,
    ) -> RenderedEmail:
        """Create the tenant-branded counterpart of a calendar delivery."""
        location = getattr(meeting, "location", None) or meeting.meeting_url
        data = MeetingEmailData(
            meeting_url=f"{self.settings.web_app_url.rstrip('/')}/meetings/{meeting.id}",
            title=meeting.title,
            organizer_name=organizer.display_name,
            start_time=self._display_datetime(meeting.start_datetime),
            end_time=self._display_datetime(meeting.end_datetime),
            timezone=meeting.timezone,
            location=location,
            join_url=meeting.meeting_url,
            description=meeting.description,
            agenda=meeting.description,
            previous_start_time=(
                self._display_datetime(previous_start_time) if previous_start_time else None
            ),
            previous_end_time=(
                self._display_datetime(previous_end_time) if previous_end_time else None
            ),
            reminder_label=reminder_label,
        )
        return EmailTemplateRegistry.render(template_key, data, sender.branding)

    @staticmethod
    def _display_datetime(value: datetime) -> str:
        return value.replace(tzinfo=value.tzinfo or UTC).strftime("%A, %B %d · %I:%M %p")

    @staticmethod
    def _retry_notification_type(channel: str) -> str:
        if channel.endswith("cancel"):
            return "meeting_cancelled"
        if channel.endswith("update"):
            return "meeting_updated"
        return "meeting_invitation"

    def _next_attempt_at(self, attempt: int, attempted_at: datetime) -> datetime | None:
        if attempt >= self.settings.delivery_max_attempts:
            return None
        delay = self.settings.delivery_retry_base_seconds * (2 ** (attempt - 1))
        return attempted_at + timedelta(seconds=delay)

    @classmethod
    def _retry_content(cls, channel: str, meeting: Meeting, organizer: User) -> tuple[str, str]:
        if channel.endswith("cancel"):
            return (
                f"Meeting cancelled: {meeting.title}",
                f"{meeting.title} scheduled for "
                f"{meeting.start_datetime.isoformat()} was cancelled.",
            )
        if channel.endswith("update"):
            return (
                f"Meeting updated: {meeting.title}",
                f"{meeting.title} now starts at {meeting.start_datetime.isoformat()} "
                f"({meeting.timezone}).",
            )
        return f"Invitation: {meeting.title}", cls._invitation_text(meeting, organizer)

    @staticmethod
    def _safe_delivery_error(error: Exception) -> str:
        if isinstance(error, EmailDeliveryError):
            return str(error)[:500]
        return f"Delivery failed ({type(error).__name__})"

    @classmethod
    def ics(
        cls,
        meeting: Meeting,
        organizer: User,
        participants: list[User],
        method: str = "REQUEST",
        status: str = "CONFIRMED",
    ) -> str:
        attendees = [
            f"ATTENDEE;CN={cls._escape(user.display_name)};RSVP=TRUE:mailto:{user.email}"
            for user in participants
        ]
        location = getattr(meeting, "location", None) or meeting.meeting_url or ""
        return "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//MeetingHQ//Meeting Invitation//EN",
                "CALSCALE:GREGORIAN",
                f"METHOD:{method}",
                "BEGIN:VEVENT",
                f"UID:{meeting.id}@meetinghq",
                f"SEQUENCE:{meeting.sequence}",
                f"DTSTAMP:{cls._ics_datetime(datetime.now(UTC))}",
                f"DTSTART:{cls._ics_datetime(meeting.start_datetime)}",
                f"DTEND:{cls._ics_datetime(meeting.end_datetime)}",
                f"SUMMARY:{cls._escape(meeting.title)}",
                f"DESCRIPTION:{cls._escape(meeting.description or '')}",
                f"LOCATION:{cls._escape(location)}",
                f"ORGANIZER;CN={cls._escape(organizer.display_name)}:mailto:{organizer.email}",
                *attendees,
                f"STATUS:{status}",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )

    @staticmethod
    def _invitation_text(meeting: Meeting, organizer: User) -> str:
        location = getattr(meeting, "location", None) or meeting.meeting_url or "Not specified"
        return (
            f"{organizer.display_name} invited you to {meeting.title}.\n\n"
            f"Agenda: {meeting.description or 'No agenda provided'}\n"
            f"Starts: {meeting.start_datetime.isoformat()} ({meeting.timezone})\n"
            f"Ends: {meeting.end_datetime.isoformat()} ({meeting.timezone})\n"
            f"Location: {location}\n"
            f"Meeting link: {meeting.meeting_url or 'Not specified'}\n\n"
            "Open MeetingHQ to Accept, Decline, or respond Tentative."
        )

    @staticmethod
    def _ics_datetime(value: datetime) -> str:
        aware = value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)
        return aware.strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        )

    @staticmethod
    def _offset_label(minutes: int) -> str:
        if minutes >= 1440:
            return f"{minutes // 1440} day"
        if minutes >= 60:
            return f"{minutes // 60} hour"
        return f"{minutes} minutes"
