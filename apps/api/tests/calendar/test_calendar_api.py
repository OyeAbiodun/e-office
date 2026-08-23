"""Calendar API integration tests."""

from httpx import AsyncClient


async def test_calendar_event_and_conflict_flow(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await organization_client.post(
        "/api/v1/calendars",
        headers=admin_headers,
        json={
            "name": "Operations",
            "type": "organization",
            "timezone": "America/Chicago",
        },
    )
    assert created.status_code == 201
    calendar_id = created.json()["data"]["id"]

    event = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/events",
        headers=admin_headers,
        json={
            "title": "Planning",
            "start_datetime": "2026-08-03T09:00:00",
            "end_datetime": "2026-08-03T10:00:00",
            "timezone": "America/Chicago",
        },
    )
    assert event.status_code == 201
    event_id = event.json()["data"]["id"]
    moved = await organization_client.patch(
        f"/api/v1/events/{event_id}",
        headers=admin_headers,
        json={
            "start_datetime": "2026-08-03T10:00:00",
            "end_datetime": "2026-08-03T11:00:00",
            "timezone": "America/Chicago",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["data"]["title"] == "Planning"
    validation = await organization_client.post(
        "/api/v1/scheduling/validate",
        headers=admin_headers,
        json={
            "calendar_ids": [calendar_id],
            "start_datetime": "2026-08-03T10:30:00",
            "end_datetime": "2026-08-03T11:30:00",
            "timezone": "America/Chicago",
        },
    )
    assert validation.status_code == 200
    assert validation.json()["data"]["valid"] is False
    assert validation.json()["data"]["conflict_count"] == 1
    deleted = await organization_client.delete(f"/api/v1/events/{event_id}", headers=admin_headers)
    assert deleted.status_code == 200
