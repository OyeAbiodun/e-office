"""Workspace lifecycle integration tests."""

from httpx import AsyncClient


async def test_workspace_create_archive_restore(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await organization_client.post(
        "/api/v1/workspaces",
        headers=admin_headers,
        json={"name": "Product", "slug": "product", "description": "Product team"},
    )
    assert created.status_code == 201
    workspace_id = created.json()["data"]["id"]
    archived = await organization_client.post(
        f"/api/v1/workspaces/{workspace_id}/archive", headers=admin_headers
    )
    assert archived.json()["data"]["archived_at"] is not None
    restored = await organization_client.post(
        f"/api/v1/workspaces/{workspace_id}/restore", headers=admin_headers
    )
    assert restored.json()["data"]["archived_at"] is None


async def test_workspace_overview_search_governance_and_integrations(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await organization_client.post(
        "/api/v1/workspaces",
        headers=admin_headers,
        json={
            "name": "Enterprise Operations",
            "slug": "enterprise-operations",
            "description": "Governed operating workspace",
            "brand_color": "#7c3aed",
            "classification": "confidential",
            "visibility": "private",
            "data_region": "us-central",
        },
    )
    assert created.status_code == 201
    workspace = created.json()["data"]
    assert workspace["classification"] == "confidential"

    searched = await organization_client.get(
        "/api/v1/workspaces?search=enterprise&classification=confidential",
        headers=admin_headers,
    )
    assert [item["id"] for item in searched.json()["data"]] == [workspace["id"]]

    overview = await organization_client.get(
        f"/api/v1/workspaces/{workspace['id']}/overview", headers=admin_headers
    )
    assert overview.status_code == 200
    assert overview.json()["data"]["member_count"] == 1
    assert overview.json()["data"]["administrator_count"] == 1
    assert overview.json()["data"]["storage_bytes"] == 0

    integrations = await organization_client.put(
        f"/api/v1/workspaces/{workspace['id']}/integrations",
        headers=admin_headers,
        json={
            "provider": "sharepoint",
            "display_name": "SharePoint",
            "enabled": True,
            "configuration": {"site": "operations"},
        },
    )
    assert integrations.status_code == 200
    assert integrations.json()["data"]["provider"] == "sharepoint"

    template = await organization_client.post(
        "/api/v1/workspaces/templates/catalog",
        headers=admin_headers,
        json={
            "name": "Operations",
            "description": "Standard operations governance",
            "configuration": {"classification": "confidential"},
        },
    )
    assert template.status_code == 201


async def test_workspace_bulk_lifecycle_filters_and_owner_protection(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    ids: list[str] = []
    for name, slug in (("Finance", "finance"), ("Legal", "legal")):
        response = await organization_client.post(
            "/api/v1/workspaces",
            headers=admin_headers,
            json={"name": name, "slug": slug},
        )
        ids.append(response.json()["data"]["id"])

    archived = await organization_client.post(
        "/api/v1/workspaces/bulk/lifecycle",
        headers=admin_headers,
        json={"workspace_ids": ids, "action": "archive"},
    )
    assert archived.status_code == 200
    assert set(archived.json()["data"]["updated_ids"]) == set(ids)

    archived_filter = await organization_client.get(
        "/api/v1/workspaces?archived=true", headers=admin_headers
    )
    archived_ids = {item["id"] for item in archived_filter.json()["data"]}
    assert set(ids).issubset(archived_ids)

    restored = await organization_client.post(
        "/api/v1/workspaces/bulk/lifecycle",
        headers=admin_headers,
        json={"workspace_ids": ids, "action": "restore"},
    )
    assert set(restored.json()["data"]["updated_ids"]) == set(ids)

    members = await organization_client.get(
        f"/api/v1/workspaces/{ids[0]}/members", headers=admin_headers
    )
    owner = members.json()["data"][0]
    removal = await organization_client.delete(
        f"/api/v1/workspaces/{ids[0]}/members/{owner['user_id']}",
        headers=admin_headers,
    )
    assert removal.status_code == 409
