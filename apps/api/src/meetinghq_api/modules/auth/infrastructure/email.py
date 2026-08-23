"""Identity email delivery through SMTP or the development outbox."""

import structlog

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.notifications.service import MeetingEmailSender

logger = structlog.get_logger(__name__)


class IdentityEmailSender:
    """Delivery adapter boundary for identity emails."""

    def __init__(self) -> None:
        self.transport = MeetingEmailSender(get_settings())

    async def send_password_reset(self, email: str, token: str) -> None:
        """Deliver a one-time password reset link."""
        await self.transport.send(
            email,
            "Reset your MeetingHQ password",
            f"Use this secure link to reset your password:\n"
            f"http://127.0.0.1:5173/reset-password?token={token}\n\n"
            "If you did not request this, you can ignore this email.",
        )
        await logger.ainfo("password_reset_requested", recipient_domain=email.rpartition("@")[2])

    async def send_verification(self, email: str, token: str) -> None:
        """Record verification delivery without logging the secret."""
        await self.transport.send(
            email,
            "Verify your MeetingHQ email",
            f"Verify your email:\nhttp://127.0.0.1:5173/verify-email?token={token}",
        )
        await logger.ainfo(
            "email_verification_requested", recipient_domain=email.rpartition("@")[2]
        )

    async def send_invitation(self, email: str, token: str) -> None:
        """Record invitation delivery without logging the secret."""
        await self.transport.send(
            email,
            "You are invited to MeetingHQ",
            f"Accept your invitation:\nhttp://127.0.0.1:5173/invitations/accept?token={token}",
        )
        await logger.ainfo(
            "organization_invitation_requested",
            recipient_domain=email.rpartition("@")[2],
        )

    async def send_temporary_password(self, email: str, temporary_password: str) -> None:
        """Deliver an administrator-issued temporary credential."""
        await self.transport.send(
            email,
            "Your MeetingHQ account is ready",
            "Sign in at http://127.0.0.1:5173/login using this temporary password:\n"
            f"{temporary_password}\n\nYou will be required to choose a new password.",
        )
        await logger.ainfo(
            "temporary_password_issued",
            recipient_domain=email.rpartition("@")[2],
        )
