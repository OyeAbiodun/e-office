"""End-to-end coverage for the usable meeting MVP."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.notifications.service import EmailDeliveryError, MeetingEmailSender


async def test_meeting_invitation_calendar_notification_and_rsvp(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    admin_headers, workspace_id = meeting_identity
    sent: list[tuple[str, str, str | None]] = []

    async def capture(
        _: MeetingEmailSender,
        recipient: str,
        subject: str,
        text: str,
        ics: str | None = None,
        message_key: str | None = None,
    ) -> str:
        sent.append((recipient, subject, ics))
        assert message_key is not None
        return "<mvp-test@meetinghq>"

    monkeypatch.setattr(MeetingEmailSender, "send", capture)
    roles = (await meeting_client.get("/api/v1/roles", headers=admin_headers)).json()["data"]
    employee_role = next(role for role in roles if role["name"] == "Employee")
    created_user = await meeting_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Meeting",
            "last_name": "Participant",
            "email": "participant@meeting-mvp.example",
            "workspace_id": workspace_id,
            "role_ids": [employee_role["id"]],
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
    assert sent[0][2] is not None
    assert "BEGIN:VCALENDAR" in sent[0][2]
    assert "METHOD:REQUEST" in sent[0][2]
    assert "SEQUENCE:0" in sent[0][2]
    assert "Room 101" in sent[0][2]

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

    duplicate_rsvp = await meeting_client.put(
        f"/api/v1/meetings/{meeting_id}/rsvp",
        headers=participant_headers,
        json={"status": "accepted"},
    )
    assert duplicate_rsvp.status_code == 200
    assert duplicate_rsvp.json()["data"]["attendance_status"] == "accepted"

    unauthorized_reschedule = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/reschedule",
        headers=participant_headers,
        json={
            "start_datetime": (start + timedelta(days=1)).isoformat(),
            "end_datetime": (start + timedelta(days=1, minutes=30)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert unauthorized_reschedule.status_code == 403

    rescheduled_start = start + timedelta(days=1)
    rescheduled = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/reschedule",
        headers=admin_headers,
        json={
            "start_datetime": rescheduled_start.isoformat(),
            "end_datetime": (rescheduled_start + timedelta(minutes=30)).isoformat(),
            "timezone": "America/New_York",
        },
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["data"]["timezone"] == "America/New_York"
    assert datetime.fromisoformat(rescheduled.json()["data"]["start_datetime"]).tzinfo is not None
    update_ics = next(ics for _, subject, ics in sent if subject.startswith("Meeting rescheduled"))
    assert update_ics is not None
    assert "METHOD:REQUEST" in update_ics
    assert "SEQUENCE:1" in update_ics
    assert "STATUS:CONFIRMED" in update_ics
    participant_events = []
    for calendar in calendars:
        events = await meeting_client.get(
            f"/api/v1/calendars/{calendar['id']}/events",
            headers=participant_headers,
        )
        participant_events.extend(
            event for event in events.json()["data"] if event["meeting_id"] == meeting_id
        )
    assert len(participant_events) == 1
    participant_start = datetime.fromisoformat(participant_events[0]["start_datetime"])
    assert participant_start.tzinfo is not None
    assert participant_start == rescheduled_start

    cancelled = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/cancel", headers=admin_headers
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    cancellation_ics = next(
        ics for _, subject, ics in sent if subject.startswith("Meeting cancelled")
    )
    assert cancellation_ics is not None
    assert "METHOD:CANCEL" in cancellation_ics
    assert "SEQUENCE:2" in cancellation_ics
    assert "STATUS:CANCELLED" in cancellation_ics

    participant_notifications = await meeting_client.get(
        "/api/v1/notifications", headers=participant_headers
    )
    types = {
        item["notification_type"]
        for item in participant_notifications.json()["data"]["notifications"]
    }
    assert {"meeting_invitation", "meeting_updated", "meeting_cancelled"} <= types

    delivery_audit = await meeting_client.get(
        "/api/v1/audit?action=meeting.delivery.accepted", headers=admin_headers
    )
    assert delivery_audit.status_code == 200
    delivery_items = delivery_audit.json()["data"]["items"]
    assert len(delivery_items) == 3
    assert all("recipient_domain" in item["metadata"] for item in delivery_items)
    assert all("@" not in item["metadata"]["recipient_domain"] for item in delivery_items)

    other_tenant = await meeting_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "MVP Isolation",
            "organization_slug": "mvp-isolation",
            "workspace_name": "Main",
            "email": "admin@mvp-isolation.example",
            "username": "mvp.isolation.admin",
            "first_name": "Isolation",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert other_tenant.status_code == 201, other_tenant.text
    other_headers = {"Authorization": f"Bearer {other_tenant.json()['data']['access_token']}"}
    isolated = await meeting_client.get(f"/api/v1/meetings/{meeting_id}", headers=other_headers)
    assert isolated.status_code == 404


async def test_transient_email_failure_does_not_rollback_the_meeting(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
    monkeypatch: MonkeyPatch,
) -> None:
    headers, workspace_id = meeting_identity
    roles = (await meeting_client.get("/api/v1/roles", headers=headers)).json()["data"]
    employee_role = next(role for role in roles if role["name"] == "Employee")
    participant = await meeting_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "first_name": "Retry",
            "last_name": "Participant",
            "email": "retry.participant@meeting-mvp.example",
            "workspace_id": workspace_id,
            "role_ids": [employee_role["id"]],
            "temporary_password": "Participant123!",
            "send_welcome_email": False,
        },
    )
    assert participant.status_code == 201, participant.text

    async def unavailable(
        _sender: MeetingEmailSender,
        _recipient: str,
        _subject: str,
        _text: str,
        _ics: str | None = None,
        _message_key: str | None = None,
    ) -> str:
        raise EmailDeliveryError("SMTP temporarily unavailable")

    monkeypatch.setattr(MeetingEmailSender, "send", unavailable)
    start = datetime.now(UTC) + timedelta(days=3)
    created = await meeting_client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "title": "Durable invitation delivery",
            "start_datetime": start.isoformat(),
            "end_datetime": (start + timedelta(minutes=30)).isoformat(),
            "timezone": "UTC",
            "attendee_ids": [participant.json()["data"]["id"]],
        },
    )
    assert created.status_code == 201, created.text

    detail = await meeting_client.get(
        f"/api/v1/meetings/{created.json()['data']['id']}", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "Durable invitation delivery"
