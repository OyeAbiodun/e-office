"""Organization profile and dashboard integration tests."""

from httpx import AsyncClient


async def test_update_organization_and_dashboard(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    updated = await organization_client.patch(
        "/api/v1/organizations/current",
        headers=admin_headers,
        json={"timezone": "America/Chicago", "brand_color": "#123abc"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["timezone"] == "America/Chicago"

    dashboard = await organization_client.get("/api/v1/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["organization_name"] == "Northstar"
    widget_ids = {widget["id"] for widget in dashboard.json()["data"]["widgets"]}
    assert {
        "workspaces",
        "teams",
        "members",
        "invitations",
    }.issubset(widget_ids)
    assert {
        "today_schedule",
        "upcoming_events",
        "availability",
        "resource_status",
        "holiday_summary",
        "quick_schedule",
    }.issubset(widget_ids)


async def test_enterprise_structure_policies_and_overview_use_live_tenant_data(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    department = await organization_client.post(
        "/api/v1/organizations/current/units",
        headers=admin_headers,
        json={
            "unit_type": "department",
            "name": "Product Engineering",
            "code": "ENG",
            "description": "Builds the MeetingHQ product.",
            "timezone": "America/Chicago",
            "working_hours": {"monday": ["09:00", "17:00"]},
        },
    )
    assert department.status_code == 201, department.text
    assert department.json()["data"]["organization_id"]

    policy = await organization_client.put(
        "/api/v1/organizations/current/policies/security",
        headers=admin_headers,
        json={
            "values": {
                "mfa_required": True,
                "session_timeout_minutes": 480,
            }
        },
    )
    assert policy.status_code == 200
    policies = await organization_client.get(
        "/api/v1/organizations/current/policies", headers=admin_headers
    )
    assert policies.json()["data"]["security"]["mfa_required"] is True

    overview = await organization_client.get(
        "/api/v1/organizations/current/overview", headers=admin_headers
    )
    assert overview.status_code == 200, overview.text
    payload = overview.json()["data"]
    assert payload["department_count"] == 1
    assert payload["member_count"] == 1
    assert payload["active_member_count"] == 1
    assert payload["workspace_count"] == 1
    assert payload["administrators"][0]["role"] == "Admin"
