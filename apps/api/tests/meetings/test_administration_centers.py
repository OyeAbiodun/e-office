"""System Health and Audit Center integration coverage."""

from httpx import AsyncClient


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
