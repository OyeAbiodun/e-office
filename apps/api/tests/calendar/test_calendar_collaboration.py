"""Production calendar collaboration and interchange integration tests."""

from httpx import AsyncClient


async def _calendar(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    me = await client.get("/api/v1/auth/me", headers=headers)
    user_id = me.json()["data"]["id"]
    created = await client.post(
        "/api/v1/calendars",
        headers=headers,
        json={
            "name": "Product delivery",
            "type": "organization",
            "timezone": "America/Chicago",
        },
    )
    assert created.status_code == 201
    return created.json()["data"]["id"], user_id


async def test_recurrence_exception_category_and_sharing_persist(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    calendar_id, user_id = await _calendar(organization_client, admin_headers)
    category = await organization_client.post(
        "/api/v1/event-categories",
        headers=admin_headers,
        json={"name": "Customer", "color": "#7c3aed"},
    )
    assert category.status_code == 201
    category_id = category.json()["data"]["id"]
    event = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/events",
        headers=admin_headers,
        json={
            "title": "Customer review",
            "start_datetime": "2026-09-07T09:00:00",
            "end_datetime": "2026-09-07T10:00:00",
            "timezone": "America/Chicago",
            "category_id": category_id,
            "recurrence": {
                "frequency": "weekly",
                "interval": 1,
                "days_of_week": [0],
                "occurrence_count": 8,
            },
        },
    )
    assert event.status_code == 201
    event_data = event.json()["data"]
    assert event_data["category_id"] == category_id
    recurrence = await organization_client.get(
        f"/api/v1/events/{event_data['id']}/recurrence", headers=admin_headers
    )
    assert recurrence.status_code == 200
    assert recurrence.json()["data"]["frequency"] == "weekly"

    exception = await organization_client.post(
        f"/api/v1/events/{event_data['id']}/exceptions",
        headers=admin_headers,
        json={
            "occurrence_start": "2026-09-14T09:00:00",
            "title": "Customer review — moved",
            "start_datetime": "2026-09-14T11:00:00",
            "end_datetime": "2026-09-14T12:00:00",
        },
    )
    assert exception.status_code == 201
    assert exception.json()["data"]["recurrence_parent_id"] == event_data["id"]

    share = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/shares",
        headers=admin_headers,
        json={"user_id": user_id, "permission": "manage"},
    )
    assert share.status_code == 201
    listed = await organization_client.get(
        f"/api/v1/calendars/{calendar_id}/shares", headers=admin_headers
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["permission"] == "manage"


async def test_ics_export_and_import_round_trip(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    calendar_id, _ = await _calendar(organization_client, admin_headers)
    created = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/events",
        headers=admin_headers,
        json={
            "title": "Architecture review",
            "description": "Decide the release boundary",
            "start_datetime": "2026-10-01T14:00:00Z",
            "end_datetime": "2026-10-01T15:00:00Z",
            "timezone": "UTC",
        },
    )
    assert created.status_code == 201
    exported = await organization_client.get(
        f"/api/v1/calendars/{calendar_id}/export.ics", headers=admin_headers
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Architecture review" in exported.text

    target_id, _ = await _calendar(organization_client, admin_headers)
    imported = await organization_client.post(
        f"/api/v1/calendars/{target_id}/import.ics",
        headers=admin_headers,
        files={"file": ("calendar.ics", exported.content, "text/calendar")},
    )
    assert imported.status_code == 200
    assert imported.json()["data"][0]["title"] == "Architecture review"
