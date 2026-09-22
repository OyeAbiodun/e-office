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


async def test_personal_calendar_is_private_until_explicitly_shared(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    workspaces = await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    roles = await organization_client.get("/api/v1/roles", headers=admin_headers)
    employee_role = next(row for row in roles.json()["data"] if row["name"] == "Employee")
    created_user = await organization_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Calendar",
            "last_name": "Participant",
            "email": "calendar.participant@northstar.example",
            "workspace_id": workspaces.json()["data"][0]["id"],
            "role_ids": [employee_role["id"]],
            "temporary_password": "CalendarAcceptance!123",
            "send_welcome_email": False,
        },
    )
    assert created_user.status_code == 201, created_user.text
    participant_id = created_user.json()["data"]["id"]
    login = await organization_client.post(
        "/api/v1/auth/login",
        json={
            "email": "calendar.participant@northstar.example",
            "password": "CalendarAcceptance!123",
        },
    )
    assert login.status_code == 200, login.text
    participant_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    personal = await organization_client.post(
        "/api/v1/calendars",
        headers=admin_headers,
        json={
            "name": "Admin private calendar",
            "type": "personal",
            "timezone": "America/Chicago",
            "visibility": "private",
        },
    )
    assert personal.status_code == 201, personal.text
    calendar_id = personal.json()["data"]["id"]
    event = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/events",
        headers=admin_headers,
        json={
            "title": "Private planning event",
            "start_datetime": "2026-10-08T09:00:00Z",
            "end_datetime": "2026-10-08T10:00:00Z",
            "timezone": "UTC",
        },
    )
    assert event.status_code == 201, event.text

    before_share = await organization_client.get("/api/v1/calendars", headers=participant_headers)
    assert calendar_id not in {row["id"] for row in before_share.json()["data"]}
    guessed = await organization_client.get(
        f"/api/v1/calendars/{calendar_id}/events", headers=participant_headers
    )
    assert guessed.status_code == 404

    shared = await organization_client.post(
        f"/api/v1/calendars/{calendar_id}/shares",
        headers=admin_headers,
        json={"user_id": participant_id, "permission": "read"},
    )
    assert shared.status_code == 201, shared.text
    after_share = await organization_client.get("/api/v1/calendars", headers=participant_headers)
    assert calendar_id in {row["id"] for row in after_share.json()["data"]}
    visible_events = await organization_client.get(
        f"/api/v1/calendars/{calendar_id}/events", headers=participant_headers
    )
    assert visible_events.status_code == 200, visible_events.text
    assert [row["title"] for row in visible_events.json()["data"]] == ["Private planning event"]
    read_only_update = await organization_client.patch(
        f"/api/v1/events/{event.json()['data']['id']}",
        headers=participant_headers,
        json={"title": "Unauthorized edit"},
    )
    assert read_only_update.status_code == 404
