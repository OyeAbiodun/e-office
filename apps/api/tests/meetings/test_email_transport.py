"""SMTP message integrity and retry behavior."""

from email.message import EmailMessage
from types import SimpleNamespace
from typing import cast

from pytest import MonkeyPatch

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.mail.models import MailMessage
from meetinghq_api.modules.mail.service import MailDeliveryAdapter
from meetinghq_api.modules.notifications.service import MeetingEmailSender
from meetinghq_api.modules.users.models import User


async def test_meeting_sender_reuses_message_id_across_transport_retry(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(
        environment="test",
        smtp_host="smtp.example.test",
        smtp_max_attempts=2,
        smtp_retry_base_seconds=0,
    )
    sender = MeetingEmailSender(
        settings,
        {
            "host": "smtp.example.test",
            "security_mode": "starttls",
            "from_email": "meetings@example.test",
            "from_name": "MeetingHQ Delivery",
            "reply_to": "support@example.test",
            "max_retry_attempts": 2,
            "retry_delay_seconds": 0,
        },
    )
    attempts: list[EmailMessage] = []

    def deliver(message: EmailMessage) -> None:
        attempts.append(message)
        if len(attempts) == 1:
            raise TimeoutError("transient test timeout")

    monkeypatch.setattr(sender, "_smtp_send", deliver)
    message_id = await sender.send(
        "participant@example.test",
        "Unicode acceptance — résumé",
        "MeetingHQ delivery body",
        message_key="delivery-123",
    )

    assert message_id == "<delivery-123@meetinghq>"
    assert len(attempts) == 2
    assert {message["Message-ID"] for message in attempts} == {message_id}
    assert all(message["Date"] for message in attempts)
    assert attempts[0]["From"] == "MeetingHQ Delivery <meetings@example.test>"
    assert attempts[0]["Reply-To"] == "support@example.test"


async def test_internal_mail_uses_stable_identity_and_configured_sender(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(environment="test")
    adapter = MailDeliveryAdapter(
        settings,
        {
            "host": "smtp.example.test",
            "from_email": "mail@example.test",
            "from_name": "MeetingHQ Mail",
            "reply_to": "help@example.test",
            "default_priority": "high",
        },
    )
    captured: list[EmailMessage] = []

    async def capture(_sender: MeetingEmailSender, message: EmailMessage) -> None:
        captured.append(message)

    monkeypatch.setattr(MeetingEmailSender, "send_message", capture)
    user = cast(User, SimpleNamespace(email="owner@example.test", display_name="Owner"))
    draft = cast(
        MailMessage,
        SimpleNamespace(
            id="8e04cbf7-a8e5-4d07-b209-b416532cc38d",
            subject="External delivery",
            body_text="Plain body",
            body_html="<p>HTML body</p>",
        ),
    )

    first = await adapter.send(user, ["external@example.test"], draft, [])
    second = await adapter.send(user, ["external@example.test"], draft, [])

    assert first == second == "<mail-8e04cbf7-a8e5-4d07-b209-b416532cc38d@meetinghq>"
    assert len(captured) == 2
    assert {message["Message-ID"] for message in captured} == {first}
    assert captured[0]["From"] == "MeetingHQ Mail <mail@example.test>"
    assert captured[0]["Reply-To"] == "help@example.test"
    assert captured[0]["X-Priority"] == "1"
    assert captured[0]["Date"]
    assert captured[0].get_body(preferencelist=("html",)) is not None
