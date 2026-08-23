"""Meeting aggregate, scheduling, collaboration, and RBAC integration tests."""

from httpx import AsyncClient

from meetinghq_api.modules.meetings.models import MeetingStatus
from meetinghq_api.modules.meetings.service import TRANSITIONS


def test_lifecycle_transition_policy_is_explicit() -> None:
    assert MeetingStatus.IN_PROGRESS in TRANSITIONS[MeetingStatus.SCHEDULED]
    assert MeetingStatus.COMPLETED in TRANSITIONS[MeetingStatus.IN_PROGRESS]
    assert MeetingStatus.DRAFT not in TRANSITIONS[MeetingStatus.COMPLETED]
    assert not TRANSITIONS[MeetingStatus.ARCHIVED]


async def test_complete_meeting_collaboration_flow(
    meeting_client: AsyncClient, meeting_identity: tuple[dict[str, str], str]
) -> None:
    headers, workspace_id = meeting_identity
    created = await meeting_client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "title": "Quarterly planning",
            "description": "Align priorities and document outcomes.",
            "start_datetime": "2027-08-03T09:00:00",
            "end_datetime": "2027-08-03T10:00:00",
            "timezone": "America/Chicago",
        },
    )
    assert created.status_code == 201, created.text
    meeting_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "scheduled"

    conflict = await meeting_client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "title": "Conflicting meeting",
            "start_datetime": "2027-08-03T09:30:00",
            "end_datetime": "2027-08-03T10:30:00",
            "timezone": "America/Chicago",
        },
    )
    assert conflict.status_code == 409

    agenda = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/agenda",
        headers=headers,
        json={"title": "Priorities", "duration_minutes": 20, "sort_order": 0},
    )
    decision = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/decisions",
        headers=headers,
        json={"title": "Fund the platform initiative"},
    )
    action = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/actions",
        headers=headers,
        json={"title": "Publish the delivery plan", "priority": "high"},
    )
    note = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/notes",
        headers=headers,
        json={"content": "The team aligned on the first release."},
    )
    assert {agenda.status_code, decision.status_code, action.status_code, note.status_code} == {201}

    started = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/transition",
        headers=headers,
        json={"status": "in_progress"},
    )
    completed = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/transition",
        headers=headers,
        json={"status": "completed"},
    )
    assert started.json()["data"]["status"] == "in_progress"
    assert completed.json()["data"]["status"] == "completed"

    detail = await meeting_client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    payload = detail.json()["data"]
    assert len(payload["agenda"]) == 1
    assert len(payload["decisions"]) == 1
    assert len(payload["action_items"]) == 1
    assert len(payload["notes"]) == 1

    history = await meeting_client.get(f"/api/v1/meetings/{meeting_id}/history", headers=headers)
    names = {item["name"] for item in history.json()["data"]}
    assert {
        "MeetingCreated",
        "AgendaUpdated",
        "DecisionCreated",
        "ActionItemCreated",
        "MeetingStarted",
        "MeetingCompleted",
    } <= names


async def test_meetings_require_authentication(meeting_client: AsyncClient) -> None:
    response = await meeting_client.get("/api/v1/meetings")
    assert response.status_code == 401


async def test_meeting_operations_are_persisted_and_analytics_are_derived(
    meeting_client: AsyncClient, meeting_identity: tuple[dict[str, str], str]
) -> None:
    headers, workspace_id = meeting_identity
    me = await meeting_client.get("/api/v1/auth/me", headers=headers)
    user_id = me.json()["data"]["id"]
    created = await meeting_client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "title": "Operations review",
            "start_datetime": "2027-09-03T09:00:00Z",
            "end_datetime": "2027-09-03T10:00:00Z",
            "timezone": "UTC",
        },
    )
    assert created.status_code == 201
    meeting_id = created.json()["data"]["id"]

    artifact = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/artifacts",
        headers=headers,
        json={
            "artifact_type": "link",
            "title": "Decision brief",
            "storage_key": "https://example.test/decision-brief",
            "metadata_json": {"source": "workspace"},
        },
    )
    recording = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        headers=headers,
        json={
            "provider": "teams",
            "status": "ready",
            "duration_seconds": 1800,
            "transcript_status": "ready",
        },
    )
    attendance = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/attendance",
        headers=headers,
        json={
            "user_id": user_id,
            "event_type": "joined",
            "occurred_at": "2027-09-03T09:00:00Z",
        },
    )
    presenter = await meeting_client.put(
        f"/api/v1/meetings/{meeting_id}/presenter-controls",
        headers=headers,
        json={"user_id": user_id, "control": "present", "enabled": True},
    )
    follow_up = await meeting_client.post(
        f"/api/v1/meetings/{meeting_id}/follow-ups",
        headers=headers,
        json={
            "follow_up_type": "summary",
            "scheduled_for": "2027-09-03T11:00:00Z",
            "payload": {"audience": "attendees"},
        },
    )
    assert {
        artifact.status_code,
        recording.status_code,
        attendance.status_code,
        presenter.status_code,
        follow_up.status_code,
    } == {200, 201}

    analytics = await meeting_client.get(
        f"/api/v1/meetings/{meeting_id}/analytics", headers=headers
    )
    assert analytics.status_code == 200
    assert analytics.json()["data"]["attendance_rate"] == 100.0
    assert analytics.json()["data"]["follow_ups_pending"] == 1

    detail = await meeting_client.get(f"/api/v1/meetings/{meeting_id}", headers=headers)
    payload = detail.json()["data"]
    assert len(payload["artifacts"]) == 1
    assert len(payload["recordings"]) == 1
    assert len(payload["attendance_events"]) == 1
    assert len(payload["presenter_controls"]) == 1
    assert len(payload["follow_ups"]) == 1
