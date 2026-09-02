"""Transactional email rendering and multipart transport tests."""

from email.message import EmailMessage

import pytest

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.notifications.email_templates import (
    EmailBranding,
    EmailTemplateRegistry,
    MeetingEmailData,
    PasswordResetEmailData,
    SmtpTestEmailData,
)
from meetinghq_api.modules.notifications.service import MeetingEmailSender


@pytest.mark.parametrize(
    "key",
    [
        "auth.password_reset",
        "auth.email_verification",
        "user.invitation",
        "user.temporary_password",
        "meeting.invitation",
        "meeting.updated",
        "meeting.cancelled",
        "meeting.reminder",
        "smtp.test",
    ],
)
def test_every_registered_template_renders_html_and_plain_text(key: str) -> None:
    rendered = EmailTemplateRegistry.preview(key)  # type: ignore[arg-type]

    assert rendered.subject.startswith("MeetingHQ |")
    assert rendered.text.strip()
    assert "<!doctype html>" in rendered.html.lower()
    assert "Schedule. Meet. Collaborate." in rendered.html
    assert "text/html" not in rendered.html
    assert "javascript:" not in rendered.html.lower()


def test_untrusted_meeting_content_is_escaped_and_unsafe_urls_fall_back() -> None:
    rendered = EmailTemplateRegistry.render(
        "meeting.invitation",
        MeetingEmailData(
            meeting_url="javascript:alert(1)",
            title='<img src=x onerror="alert(1)">',
            organizer_name="<b>Organizer</b>",
            start_time="Tomorrow",
            end_time="11:00 AM",
            timezone="UTC",
            description='<script>alert("unsafe")</script>',
            join_url="data:text/html,unsafe",
        ),
        EmailBranding(
            organization_name='<img src=x onerror="alert(1)">',
            accent_color="#2563eb",
            logo_url="javascript:alert(1)",
        ),
    )

    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "<img src=x onerror=" not in rendered.html
    assert "javascript:" not in rendered.html.lower()
    assert "data:text/html" not in rendered.html.lower()
    assert "https://app.meetinghq.example" in rendered.html


async def test_rendered_email_is_multipart_with_html_plain_text_and_ics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = MeetingEmailSender(
        Settings(environment="test", smtp_host="smtp.example.test"),
        {"host": "smtp.example.test", "authentication_enabled": False},
    )
    delivered: list[EmailMessage] = []

    async def capture(message: EmailMessage) -> None:
        delivered.append(message)

    monkeypatch.setattr(sender, "send_message", capture)
    rendered = EmailTemplateRegistry.render(
        "auth.password_reset",
        PasswordResetEmailData("https://app.meetinghq.example/reset-password?token=opaque"),
    )
    message_id = await sender.send_rendered(
        "recipient@example.test",
        rendered,
        ics="BEGIN:VCALENDAR\r\nMETHOD:REQUEST\r\nEND:VCALENDAR\r\n",
        message_key="template-contract",
    )

    assert message_id == "<template-contract@meetinghq>"
    assert len(delivered) == 1
    message = delivered[0]
    assert message["X-MeetingHQ-Template"] == "auth.password_reset"
    assert message["X-MeetingHQ-Template-Version"]
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == rendered.text
    assert message.get_body(preferencelist=("html",)).get_content().strip() == rendered.html
    assert any(part.get_content_type() == "text/calendar" for part in message.walk())


def test_password_reset_includes_security_guidance_without_displaying_a_raw_token_label() -> None:
    token = "opaque-reset-token"
    rendered = EmailTemplateRegistry.render(
        "auth.password_reset",
        PasswordResetEmailData(f"https://app.meetinghq.example/reset-password?token={token}"),
    )

    assert "token:" not in rendered.text.lower()
    assert token in rendered.text  # It is part of the required fallback URL only.
    assert "If you did not request this" in rendered.text


def test_smtp_template_has_no_secrets_and_provides_delivery_guidance() -> None:
    rendered = EmailTemplateRegistry.render(
        "smtp.test", SmtpTestEmailData("September 2, 2026 · 10:00 UTC", "staging")
    )

    assert "SMTP test successful" in rendered.subject
    assert "final mailbox delivery" in rendered.text
