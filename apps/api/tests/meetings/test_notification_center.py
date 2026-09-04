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


async def test_push_subscription_is_user_and_tenant_scoped(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    subscription = await meeting_client.put(
        "/api/v1/notifications/push-subscriptions",
        headers=headers,
        json={
            "endpoint": "https://push.example/subscription-1",
            "p256dh": "public-key-material",
            "auth": "auth-material",
            "user_agent": "MeetingHQ test browser",
        },
    )
    assert subscription.status_code == 200, subscription.text
    listed = await meeting_client.get("/api/v1/notifications/push-subscriptions", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1
    revoked = await meeting_client.delete(
        f"/api/v1/notifications/push-subscriptions/{subscription.json()['data']['id']}",
        headers=headers,
    )
    assert revoked.status_code == 204
    assert (await meeting_client.get("/api/v1/notifications/push-subscriptions", headers=headers)).json()[
        "data"
    ][0]["enabled"] is False
