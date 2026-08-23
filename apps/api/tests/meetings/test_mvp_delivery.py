"""End-to-end coverage for the usable meeting MVP."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.notifications.service import MeetingEmailSender


async def test_meeting_invitation_calendar_notification_and_rsvp(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    admin_headers, workspace_id = meeting_identity
    sent: list[tuple[str, str | None]] = []

    async def capture(
        _: MeetingEmailSender,
        recipient: str,
        subject: str,
        text: str,
        ics: str | None = None,
    ) -> str:
        sent.append((recipient, ics))
        return "<mvp-test@meetinghq>"

    monkeypatch.setattr(MeetingEmailSender, "send", capture)
    roles = (await meeting_client.get("/api/v1/roles", headers=admin_headers)).json()["data"]
    admin_role = next(role for role in roles if role["name"] == "Admin")
    created_user = await meeting_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Meeting",
            "last_name": "Participant",
            "email": "participant@meeting-mvp.example",
            "workspace_id": workspace_id,
            "role_ids": [admin_role["id"]],
            "temporary_password": "Participant123!",
            "send_welcome_email": False,
        },
    )
    assert created_user.status_code == 201, created_user.text
    participant_id = created_user.json()["data"]["id"]
    start = datetime.now(UTC) + timedelta(days=2)
    created = await meeting_client.post(
        "/api/v1/meetings",
        headers=admin_headers,
        json={
            "workspace_id": workspace_id,
            "title": "MVP delivery verification",
            "agenda": "Verify the invitation workflow",
            "location_type": "hybrid",
            "location": "Room 101",
            "meeting_url": "https://meet.example.test/mvp",
            "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(minutes=30)).isoformat(),
            "timezone": "America/Chicago",
            "attendee_ids": [participant_id],
        },
    )
    assert created.status_code == 201, created.text
    meeting_id = created.json()["data"]["id"]
    assert sent and sent[0][0] == "participant@meeting-mvp.example"
    assert sent[0][1] is not None
    assert "BEGIN:VCALENDAR" in sent[0][1]
    assert "Room 101" in sent[0][1]

    participant_login = await meeting_client.post(
        "/api/v1/auth/login",
        json={
            "email": "participant@meeting-mvp.example",
            "password": "Participant123!",
        },
    )
    assert participant_login.status_code == 200
    participant_headers = {
        "Authorization": f"Bearer {participant_login.json()['data']['access_token']}"
    }
    notifications = await meeting_client.get("/api/v1/notifications", headers=participant_headers)
    assert notifications.json()["data"]["unread"] == 1
    assert (
        notifications.json()["data"]["notifications"][0]["notification_type"]
        == "meeting_invitation"
    )

    calendars = (await meeting_client.get("/api/v1/calendars", headers=participant_headers)).json()[
        "data"
    ]
    participant_events = []
    for calendar in calendars:
        events = await meeting_client.get(
            f"/api/v1/calendars/{calendar['id']}/events",
            headers=participant_headers,
        )
        participant_events.extend(events.json()["data"])
    assert any(event["meeting_id"] == meeting_id for event in participant_events)

    rsvp = await meeting_client.put(
        f"/api/v1/meetings/{meeting_id}/rsvp",
        headers=participant_headers,
        json={"status": "accepted"},
    )
    assert rsvp.status_code == 200
    assert rsvp.json()["data"]["attendance_status"] == "accepted"

    detail = await meeting_client.get(f"/api/v1/meetings/{meeting_id}", headers=admin_headers)
    attendee = next(
        row for row in detail.json()["data"]["attendees"] if row["user_id"] == participant_id
    )
    assert attendee["display_name"] == "Meeting Participant"
    assert attendee["attendance_status"] == "accepted"
