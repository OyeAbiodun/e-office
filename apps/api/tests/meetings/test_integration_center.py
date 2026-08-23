"""External provider governance and protected configuration coverage."""

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.integrations.service import IntegrationService


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
