"""Identity email delivery through SMTP or the development outbox."""

import uuid
from urllib.parse import urlencode

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
from meetinghq_api.modules.notifications.email_templates import (
    EmailTemplateRegistry,
    PasswordResetEmailData,
    TemporaryPasswordEmailData,
    UserInvitationEmailData,
    VerificationEmailData,
)
from meetinghq_api.modules.notifications.service import MeetingEmailSender

logger = structlog.get_logger(__name__)


class IdentityEmailSender:
    """Delivery adapter boundary for identity emails."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def _transport(self, organization_id: uuid.UUID | None) -> MeetingEmailSender:
        if self.session is None:
            return MeetingEmailSender(self.settings)
        return await MeetingEmailSender.for_organization(
            self.session, self.settings, organization_id
        )

    def _application_link(self, path: str, **query: str) -> str:
        suffix = f"?{urlencode(query)}" if query else ""
        return f"{self.settings.web_app_url}{path}{suffix}"

    async def send_password_reset(
        self, email: str, token: str, organization_id: uuid.UUID | None = None
    ) -> None:
        """Deliver a one-time password reset link."""
        transport = await self._transport(organization_id)
        rendered = EmailTemplateRegistry.render(
            "auth.password_reset",
            PasswordResetEmailData(
                self._application_link("/reset-password", token=token),
                expires_in=f"{self.settings.password_reset_ttl_minutes} minutes",
            ),
            transport.branding,
        )
        await transport.send_rendered(email, rendered)
        await logger.ainfo("password_reset_requested", recipient_domain=email.rpartition("@")[2])

    async def send_verification(
        self, email: str, token: str, organization_id: uuid.UUID | None = None
    ) -> None:
        """Record verification delivery without logging the secret."""
        transport = await self._transport(organization_id)
        rendered = EmailTemplateRegistry.render(
            "auth.email_verification",
            VerificationEmailData(self._application_link("/verify-email", token=token)),
            transport.branding,
        )
        await transport.send_rendered(email, rendered)
        await logger.ainfo(
            "email_verification_requested", recipient_domain=email.rpartition("@")[2]
        )

    async def send_invitation(
        self, email: str, token: str, organization_id: uuid.UUID | None = None
    ) -> None:
        """Record invitation delivery without logging the secret."""
        transport = await self._transport(organization_id)
        rendered = EmailTemplateRegistry.render(
            "user.invitation",
            UserInvitationEmailData(
                self._application_link("/invitations/accept", token=token),
                transport.branding.organization_name,
            ),
            transport.branding,
        )
        await transport.send_rendered(email, rendered)
        await logger.ainfo(
            "organization_invitation_requested",
            recipient_domain=email.rpartition("@")[2],
        )

    async def send_temporary_password(
        self,
        email: str,
        temporary_password: str,
        organization_id: uuid.UUID | None = None,
    ) -> None:
        """Deliver an administrator-issued temporary credential."""
        transport = await self._transport(organization_id)
        rendered = EmailTemplateRegistry.render(
            "user.temporary_password",
            TemporaryPasswordEmailData(self._application_link("/login"), temporary_password),
            transport.branding,
        )
        await transport.send_rendered(email, rendered)
        await logger.ainfo(
            "temporary_password_issued",
            recipient_domain=email.rpartition("@")[2],
        )
