"""Configuration-driven platform management integration coverage."""

from httpx import AsyncClient


async def test_super_admin_style_administrator_can_manage_features_and_menus(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    features = await meeting_client.get("/api/v1/platform/features", headers=headers)
    assert features.status_code == 200
    assert len(features.json()["data"]) >= 20

    disabled = await meeting_client.patch(
        "/api/v1/platform/features/calendar",
        headers=headers,
        json={"enabled": False, "maintenance_mode": True, "release_stage": "internal"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["maintenance_mode"] is True

    renamed = await meeting_client.patch(
        "/api/v1/platform/menus/meetings",
        headers=headers,
        json={"label": "Sessions", "position": 1, "badge": "MVP"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["label"] == "Sessions"

    configuration = await meeting_client.put(
        "/api/v1/platform/configuration/meeting_defaults",
        headers=headers,
        json={
            "category": "meetings",
            "value": {"duration_minutes": 45, "timezone": "America/Chicago"},
        },
    )
    assert configuration.status_code == 200
    listed = await meeting_client.get("/api/v1/platform/configuration", headers=headers)
    assert listed.json()["data"][0]["value"]["duration_minutes"] == 45
