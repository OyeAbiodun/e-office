"""Notification Center preferences and tenant-safe inbox coverage."""

from httpx import AsyncClient


async def test_notification_preferences_and_inbox_filters(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity

    initial = await meeting_client.get("/api/v1/notifications/preferences/me", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["in_app_enabled"] is True

    updated = await meeting_client.put(
        "/api/v1/notifications/preferences/me",
        headers=headers,
        json={
            "in_app_enabled": True,
            "email_enabled": False,
            "browser_enabled": True,
            "quiet_hours_enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "timezone": "America/Chicago",
            "category_rules": {"mentions": {"browser": True}},
            "delivery_rules": {"urgent": ["in_app", "browser"]},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["quiet_hours_start"] == "22:00"
    assert updated.json()["data"]["browser_enabled"] is True

    inbox = await meeting_client.get(
        "/api/v1/notifications?category=meetings&unread_only=true",
        headers=headers,
    )
    assert inbox.status_code == 200
    assert inbox.json()["data"]["notifications"] == []

    read_all = await meeting_client.post("/api/v1/notifications/read-all", headers=headers)
    assert read_all.status_code == 200
    assert read_all.json()["data"]["updated"] == 0
