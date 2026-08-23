"""Team and membership integration tests."""

from httpx import AsyncClient


async def test_team_creation_assigns_owner(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    workspaces = await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    workspace_id = workspaces.json()["data"][0]["id"]
    team = await organization_client.post(
        "/api/v1/teams",
        headers=admin_headers,
        json={"workspace_id": workspace_id, "name": "Platform", "slug": "platform"},
    )
    assert team.status_code == 201
    members = await organization_client.get(
        f"/api/v1/teams/{team.json()['data']['id']}/members", headers=admin_headers
    )
    assert members.status_code == 200
    assert members.json()["data"][0]["role"] == "owner"


async def test_team_product_lifecycle_channels_documents_and_dashboard(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    workspace_id = (
        await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    ).json()["data"][0]["id"]
    created = await organization_client.post(
        "/api/v1/teams",
        headers=admin_headers,
        json={
            "workspace_id": workspace_id,
            "name": "Enterprise Launch",
            "slug": "enterprise-launch",
            "description": "Cross-functional launch team",
            "classification": "confidential",
            "visibility": "private",
            "color": "#7c3aed",
        },
    )
    assert created.status_code == 201, created.text
    team_id = created.json()["data"]["id"]

    searched = await organization_client.get(
        "/api/v1/teams?search=enterprise&visibility=private",
        headers=admin_headers,
    )
    assert [item["id"] for item in searched.json()["data"]] == [team_id]

    channel = await organization_client.post(
        f"/api/v1/teams/{team_id}/channels",
        headers=admin_headers,
        json={
            "name": "Launch announcements",
            "description": "Moderated launch updates",
            "channel_kind": "announcement",
            "visibility": "members",
            "moderation_enabled": True,
            "read_only": True,
        },
    )
    assert channel.status_code == 201, channel.text
    channel_id = channel.json()["data"]["id"]
    assert channel.json()["data"]["moderation_enabled"] is True

    preference = await organization_client.put(
        f"/api/v1/teams/{team_id}/channels/{channel_id}/preference",
        headers=admin_headers,
        json={"favorite": True, "pinned": True},
    )
    assert preference.status_code == 200
    channels = await organization_client.get(
        f"/api/v1/teams/{team_id}/channels?channel_kind=announcement",
        headers=admin_headers,
    )
    assert channels.json()["data"][0]["favorite"] is True
    assert channels.json()["data"][0]["pinned"] is True

    for document_type in ("wiki", "note"):
        document = await organization_client.post(
            f"/api/v1/teams/{team_id}/documents",
            headers=admin_headers,
            json={
                "document_type": document_type,
                "title": f"Launch {document_type}",
                "content": "Persisted collaboration knowledge.",
            },
        )
        assert document.status_code == 201

    integration = await organization_client.put(
        f"/api/v1/teams/{team_id}/integrations",
        headers=admin_headers,
        json={
            "provider": "power-bi",
            "display_name": "Power BI",
            "enabled": True,
            "configuration": {"dashboard": "launch"},
        },
    )
    assert integration.status_code == 200

    overview = await organization_client.get(
        f"/api/v1/teams/{team_id}/overview", headers=admin_headers
    )
    payload = overview.json()["data"]
    assert payload["owner_count"] == 1
    assert payload["channel_count"] == 1
    assert payload["wiki_count"] == 1
    assert payload["note_count"] == 1
    assert payload["app_count"] == 1
    assert payload["announcement_count"] == 1

    archived = await organization_client.post(
        f"/api/v1/teams/{team_id}/archive", headers=admin_headers
    )
    assert archived.json()["data"]["archived_at"] is not None
    restored = await organization_client.post(
        f"/api/v1/teams/{team_id}/restore", headers=admin_headers
    )
    assert restored.json()["data"]["archived_at"] is None

    archived_channel = await organization_client.post(
        f"/api/v1/teams/{team_id}/channels/{channel_id}/archive",
        headers=admin_headers,
    )
    assert archived_channel.status_code == 200
    hidden = await organization_client.get(
        f"/api/v1/teams/{team_id}/channels?archived=false",
        headers=admin_headers,
    )
    assert hidden.json()["data"] == []
    restored_channel = await organization_client.post(
        f"/api/v1/teams/{team_id}/channels/{channel_id}/restore",
        headers=admin_headers,
    )
    assert restored_channel.status_code == 200
