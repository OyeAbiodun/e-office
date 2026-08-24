"""Identity email delivery through SMTP or the development outbox."""

import uuid
from urllib.parse import urlencode

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings, get_settings
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
        await (await self._transport(organization_id)).send(
            email,
            "Reset your MeetingHQ password",
            "Use this secure link to reset your password:\n"
            f"{self._application_link('/reset-password', token=token)}\n\n"
            "If you did not request this, you can ignore this email.",
        )
        await logger.ainfo("password_reset_requested", recipient_domain=email.rpartition("@")[2])

    async def send_verification(
        self, email: str, token: str, organization_id: uuid.UUID | None = None
    ) -> None:
        """Record verification delivery without logging the secret."""
        await (await self._transport(organization_id)).send(
            email,
            "Verify your MeetingHQ email",
            f"Verify your email:\n{self._application_link('/verify-email', token=token)}",
        )
        await logger.ainfo(
            "email_verification_requested", recipient_domain=email.rpartition("@")[2]
        )

    async def send_invitation(
        self, email: str, token: str, organization_id: uuid.UUID | None = None
    ) -> None:
        """Record invitation delivery without logging the secret."""
        await (await self._transport(organization_id)).send(
            email,
            "You are invited to MeetingHQ",
            "Accept your invitation:\n"
            f"{self._application_link('/invitations/accept', token=token)}",
        )
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
        await (await self._transport(organization_id)).send(
            email,
            "Your MeetingHQ account is ready",
            f"Sign in at {self._application_link('/login')} using this temporary password:\n"
            f"{temporary_password}\n\nYou will be required to choose a new password.",
        )
        await logger.ainfo(
            "temporary_password_issued",
            recipient_domain=email.rpartition("@")[2],
        )
