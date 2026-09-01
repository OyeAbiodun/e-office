"""System Health and Audit Center integration coverage."""

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.notifications.service import MeetingEmailSender


async def test_system_health_returns_live_operational_snapshot(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity

    response = await meeting_client.get("/api/v1/system-health", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert 0 <= data["score"] <= 100
    assert data["version"]
    assert data["uptime_seconds"] >= 0
    assert {component["key"] for component in data["components"]} >= {
        "api",
        "database",
        "redis",
        "workers",
        "scheduler",
        "smtp",
        "storage",
        "websocket",
        "integrations",
    }
    assert data["queue"].keys() == {"pending", "failed", "delivered"}

    components = data["components"]
    expected_score = max(
        0,
        100
        - sum(
            15
            for component in components
            if component["requirement"] in {"required", "configured"}
            and component["status"] == "not_configured"
        )
        - sum(
            10
            for component in components
            if component["requirement"] in {"required", "configured"}
            and component["status"] == "degraded"
        )
        - sum(
            25
            for component in components
            if component["requirement"] in {"required", "configured"}
            and component["status"] == "unavailable"
        ),
    )
    assert data["score"] == expected_score

    smtp = next(component for component in components if component["key"] == "smtp")
    assert smtp["status"] == "not_configured"
    assert smtp["requirement"] == "recommended"
    assert smtp["configured"] is False

    storage = next(component for component in components if component["key"] == "storage")
    disk = next(component for component in components if component["key"] == "disk")
    assert storage["details"]["path"] == disk["details"]["path"]
    assert storage["details"]["total_bytes"] == disk["details"]["total_bytes"]
    assert abs(storage["details"]["used_bytes"] - disk["details"]["used_bytes"]) < 10 * 1024 * 1024


async def test_audit_center_lists_and_exports_only_current_tenant(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    second = await meeting_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Tenant",
            "organization_slug": "other-tenant",
            "workspace_name": "Other Workspace",
            "email": "admin@other.example",
            "username": "other.admin",
            "first_name": "Other",
            "last_name": "Admin",
            "password": "Secure!Password456",
        },
    )
    assert second.status_code == 201

    response = await meeting_client.get("/api/v1/audit", headers=headers)
    exported = await meeting_client.get("/api/v1/audit/export", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    assert all(item["user_name"] != "Other Admin" for item in data["items"])
    assert all(item["organization_id"] for item in data["items"])
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "admin@other.example" not in exported.text


async def test_system_health_validates_tenant_smtp_configuration(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    headers, _ = meeting_identity
    configured = await meeting_client.put(
        "/api/v1/integrations/smtp",
        headers=headers,
        json={
            "values": {
                "host": "smtp.example.test",
                "port": 587,
                "username": "mailer@example.test",
                "password": "tenant-secret-not-returned",
                "from_email": "meetings@example.test",
            }
        },
    )
    assert configured.status_code == 200

    async def successful_probe(_: MeetingEmailSender) -> None:
        return None

    monkeypatch.setattr(MeetingEmailSender, "test_connection", successful_probe)
    response = await meeting_client.get("/api/v1/system-health", headers=headers)

    assert response.status_code == 200
    smtp = next(
        component
        for component in response.json()["data"]["components"]
        if component["key"] == "smtp"
    )
    assert smtp["status"] == "healthy"
    assert smtp["requirement"] == "configured"
    assert smtp["configured"] is True
    assert smtp["details"]["mode"] == "smtp"
    assert smtp["details"]["validated"] is True
    assert smtp["details"]["configured"] is True
    assert smtp["details"]["enabled"] is True
    assert smtp["details"]["recent_failures"] == 0
    assert smtp["details"]["last_validation"]
