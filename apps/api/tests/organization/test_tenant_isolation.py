"""Cross-tenant isolation contract tests for every current product boundary."""

from httpx import AsyncClient


async def _register_tenant(
    client: AsyncClient, *, slug: str, email: str
) -> tuple[dict[str, str], dict[str, object]]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": slug.title(),
            "organization_slug": slug,
            "workspace_name": f"{slug.title()} HQ",
            "email": email,
            "username": f"{slug}.admin",
            "first_name": slug.title(),
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()["data"]
    return (
        {"Authorization": f"Bearer {payload['access_token']}"},
        payload,
    )


async def test_tenant_resources_are_undiscoverable_across_all_current_boundaries(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    other_headers, other_identity = await _register_tenant(
        organization_client,
        slug="contoso",
        email="admin@contoso.example",
    )
    other_user_id = other_identity["user"]["id"]
    other_workspaces = await organization_client.get("/api/v1/workspaces", headers=other_headers)
    other_workspace_id = other_workspaces.json()["data"][0]["id"]
    other_calendar = await organization_client.post(
        "/api/v1/calendars",
        headers=other_headers,
        json={
            "workspace_id": other_workspace_id,
            "name": "Contoso Operations",
            "type": "workspace",
            "timezone": "UTC",
        },
    )
    assert other_calendar.status_code == 201, other_calendar.text
    other_calendar_id = other_calendar.json()["data"]["id"]

    other_team = await organization_client.post(
        "/api/v1/teams",
        headers=other_headers,
        json={
            "workspace_id": other_workspace_id,
            "name": "Contoso Leadership",
            "slug": "leadership",
        },
    )
    assert other_team.status_code == 201
    other_team_id = other_team.json()["data"]["id"]

    other_channel = await organization_client.post(
        "/api/v1/conversations",
        headers=other_headers,
        json={
            "workspace_id": other_workspace_id,
            "team_id": other_team_id,
            "type": "public_team",
            "name": "Contoso private operations",
            "channel_kind": "private",
        },
    )
    assert other_channel.status_code == 201
    other_channel_id = other_channel.json()["data"]["id"]

    direct_probes = [
        f"/api/v1/users/{other_user_id}",
        f"/api/v1/workspaces/{other_workspace_id}",
        f"/api/v1/teams/{other_team_id}/members",
        f"/api/v1/calendars/{other_calendar_id}",
        f"/api/v1/conversations/{other_channel_id}",
    ]
    for path in direct_probes:
        response = await organization_client.get(path, headers=admin_headers)
        assert response.status_code == 404, (path, response.text)

    northstar_users = await organization_client.get("/api/v1/users", headers=admin_headers)
    northstar_workspaces = await organization_client.get(
        "/api/v1/workspaces", headers=admin_headers
    )
    northstar_teams = await organization_client.get("/api/v1/teams", headers=admin_headers)
    northstar_calendars = await organization_client.get("/api/v1/calendars", headers=admin_headers)
    northstar_channels = await organization_client.get(
        "/api/v1/conversations", headers=admin_headers
    )

    assert other_user_id not in {item["id"] for item in northstar_users.json()["data"]}
    assert other_workspace_id not in {item["id"] for item in northstar_workspaces.json()["data"]}
    assert other_team_id not in {item["id"] for item in northstar_teams.json()["data"]}
    assert other_calendar_id not in {item["id"] for item in northstar_calendars.json()["data"]}
    assert other_channel_id not in {item["id"] for item in northstar_channels.json()["data"]}
