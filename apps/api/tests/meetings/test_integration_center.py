"""External provider governance and protected configuration coverage."""

import smtplib
import socket
import ssl

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.integrations.service import IntegrationService
from meetinghq_api.modules.notifications.service import EmailDeliveryError, MeetingEmailSender


def test_smtp_failures_are_classified_without_exposing_provider_details() -> None:
    cases = (
        (
            smtplib.SMTPAuthenticationError(535, b"provider-secret-diagnostic"),
            "SMTP authentication failed. Verify the username and app password.",
        ),
        (
            TimeoutError("provider-secret-diagnostic"),
            "SMTP connection timed out. Verify the host, port, and firewall rules.",
        ),
        (
            ssl.SSLError("provider-secret-diagnostic"),
            "SMTP TLS negotiation failed. Verify the security mode and certificate.",
        ),
        (
            smtplib.SMTPRecipientsRefused({"invalid@example.com": (550, b"rejected")}),
            "SMTP rejected the recipient address.",
        ),
        (
            socket.gaierror("provider-secret-diagnostic"),
            "Unable to resolve the SMTP server hostname.",
        ),
        (
            ConnectionRefusedError("provider-secret-diagnostic"),
            "Unable to connect to the SMTP server. Verify the host and port.",
        ),
    )
    for error, expected in cases:
        diagnostic = IntegrationService._safe_smtp_error(error)
        assert diagnostic == expected
        assert "provider-secret-diagnostic" not in diagnostic


async def test_integration_center_separates_availability_from_credentials(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    headers, _ = meeting_identity

    providers = await meeting_client.get("/api/v1/integrations", headers=headers)
    assert providers.status_code == 200
    assert len(providers.json()["data"]) >= 20
    smtp = next(item for item in providers.json()["data"] if item["key"] == "smtp")
    assert smtp["configured"] is False
    assert "values" not in smtp

    disabled = await meeting_client.patch(
        "/api/v1/platform/features/smtp",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200

    configured = await meeting_client.put(
        "/api/v1/integrations/smtp",
        headers=headers,
        json={
            "values": {
                "host": "smtp.example.test",
                "port": "587",
                "username": "mailer@example.test",
                "password": "never-return-this-secret",
            }
        },
    )
    assert configured.status_code == 200
    assert configured.json()["data"]["configured"] is True
    assert configured.json()["data"]["validated"] is False
    assert configured.json()["data"]["enabled"] is False
    assert "values" not in configured.json()["data"]
    assert "never-return-this-secret" not in configured.text

    async def probe(
        _: IntegrationService,
        _provider: object,
        _values: dict[str, object],
    ) -> str:
        return "Provider authenticated successfully."

    monkeypatch.setattr(IntegrationService, "_probe", probe)
    tested = await meeting_client.post("/api/v1/integrations/smtp/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["data"]["status"] == "healthy"
    assert tested.json()["data"]["latency_ms"] >= 1

    validated = await meeting_client.get("/api/v1/integrations", headers=headers)
    smtp = next(item for item in validated.json()["data"] if item["key"] == "smtp")
    assert smtp["validated"] is True
    assert smtp["last_tested_at"] is not None

    configuration = await meeting_client.get("/api/v1/platform/configuration", headers=headers)
    assert all(item["key"] != "integration.smtp" for item in configuration.json()["data"])

    disconnected = await meeting_client.delete("/api/v1/integrations/smtp", headers=headers)
    assert disconnected.status_code == 200
    assert disconnected.json()["data"]["configured"] is False

    audit = await meeting_client.get("/api/v1/audit?search=integrations.", headers=headers)
    actions = {item["action"] for item in audit.json()["data"]["items"]}
    assert {"integrations.update", "integrations.create", "integrations.delete"} <= actions


async def test_smtp_administration_preserves_write_only_secret_and_uses_shared_transport(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    headers, _ = meeting_identity
    initial = await meeting_client.get("/api/v1/integrations/smtp/configuration", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["state"] == "not_configured"

    payload = {
        "provider_display_name": "Transactional SMTP",
        "host": "smtp.example.test",
        "port": 587,
        "security_mode": "starttls",
        "allow_insecure": False,
        "connection_timeout": 12,
        "authentication_enabled": True,
        "authentication_method": "password",
        "username": "mailer@example.com",
        "password": "write-only-provider-secret",
        "from_email": "meetings@example.com",
        "from_name": "MeetingHQ",
        "reply_to": "support@example.com",
        "return_path": "bounces@example.com",
        "enabled": True,
        "max_retry_attempts": 4,
        "retry_delay_seconds": 2,
        "timeout_seconds": 18,
        "default_priority": "normal",
    }
    saved = await meeting_client.put(
        "/api/v1/integrations/smtp/configuration", headers=headers, json=payload
    )
    assert saved.status_code == 200
    body = saved.json()["data"]
    assert body["password_configured"] is True
    assert body["password_mask"] == "••••••••••••"
    assert "write-only-provider-secret" not in saved.text
    assert body["revision"] == 1

    payload["provider_display_name"] = "Primary Transactional SMTP"
    payload["password"] = ""
    updated = await meeting_client.put(
        "/api/v1/integrations/smtp/configuration", headers=headers, json=payload
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["revision"] == 2
    assert updated.json()["data"]["password_configured"] is True

    observed = {"password_preserved": False, "recipient": ""}

    async def connected(sender: MeetingEmailSender) -> None:
        observed["password_preserved"] = bool(sender.values.get("password"))

    async def accepted(
        sender: MeetingEmailSender,
        recipient: str,
        _subject: str,
        _text: str,
        _ics: str | None = None,
        _message_key: str | None = None,
    ) -> str:
        observed["password_preserved"] = bool(sender.values.get("password"))
        observed["recipient"] = recipient
        return "<test-message@meetinghq>"

    monkeypatch.setattr(MeetingEmailSender, "test_connection", connected)
    tested = await meeting_client.post("/api/v1/integrations/smtp/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["data"]["status"] == "healthy"

    monkeypatch.setattr(MeetingEmailSender, "send", accepted)
    test_email = await meeting_client.post(
        "/api/v1/integrations/smtp/test-email",
        headers=headers,
        json={"recipient": "operator@example.com"},
    )
    assert test_email.status_code == 200
    assert test_email.json()["data"]["status"] == "accepted"
    assert observed == {
        "password_preserved": True,
        "recipient": "operator@example.com",
    }

    async def rejected(
        _sender: MeetingEmailSender,
        _recipient: str,
        _subject: str,
        _text: str,
        _ics: str | None = None,
        _message_key: str | None = None,
    ) -> str:
        raise EmailDeliveryError("SMTP authentication failed")

    monkeypatch.setattr(MeetingEmailSender, "send", rejected)
    failed_email = await meeting_client.post(
        "/api/v1/integrations/smtp/test-email",
        headers=headers,
        json={"recipient": "operator@example.com"},
    )
    assert failed_email.status_code == 200
    assert failed_email.json()["data"]["status"] == "failed"
    assert failed_email.json()["data"]["message"] == (
        "SMTP authentication failed. Verify the username and app password."
    )
    failed_state = await meeting_client.get(
        "/api/v1/integrations/smtp/configuration", headers=headers
    )
    assert failed_state.json()["data"]["state"] == "failed"

    audit = await meeting_client.get("/api/v1/integrations/smtp/audit", headers=headers)
    actions = {item["action"] for item in audit.json()["data"]}
    assert {
        "smtp.configuration_created",
        "smtp.configuration_updated",
        "smtp.test_email_requested",
        "smtp.test_email_accepted",
        "smtp.test_email_failed",
        "integrations.connection_tested",
    } <= actions
