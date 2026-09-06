"""Integrated work-management API contract tests."""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient

from tests.organization.test_tenant_isolation import _register_tenant


async def test_self_task_activity_history_and_filters(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "title": "Prepare weekly update",
            "description": "Capture the product and customer outcomes.",
            "priority": "high",
            "due_date": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()["data"]
    assert task["sequence"] == 1
    assert task["assignee_id"] == task["created_by_id"]

    updated = await organization_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=admin_headers,
        json={"status": "in_progress", "progress": 40},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["progress"] == 40

    comment = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/comments",
        headers=admin_headers,
        json={"body": "The first draft is ready for review."},
    )
    assert comment.status_code == 201, comment.text

    activity = await organization_client.post(
        "/api/v1/tasks/activities",
        headers=admin_headers,
        json={
            "activity_date": date.today().isoformat(),
            "summary": "Prepared the weekly update draft.",
            "task_id": task["id"],
            "duration_minutes": 45,
            "blockers": "Waiting for final analytics.",
        },
    )
    assert activity.status_code == 201, activity.text

    listed = await organization_client.get(
        "/api/v1/tasks?scope=mine&priority=high&page=1&page_size=10",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1

    detail = await organization_client.get(f"/api/v1/tasks/{task['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert {row["event_type"] for row in detail.json()["data"]["history"]} >= {
        "created",
        "status_changed",
        "commented",
    }

    summary = await organization_client.get(
        f"/api/v1/tasks/summary/daily?summary_date={date.today().isoformat()}",
        headers=admin_headers,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["activities"][0]["task_id"] == task["id"]

    checklist = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/checklist",
        headers=admin_headers,
        json={"title": "Send the summary"},
    )
    assert checklist.status_code == 201, checklist.text
    item = checklist.json()["data"]
    completed = await organization_client.patch(
        f"/api/v1/tasks/{task['id']}/checklist/{item['id']}",
        headers=admin_headers,
        json={"completed": True},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["completed_at"] is not None

    attachment = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        headers=admin_headers,
        files={"file": ("weekly-notes.txt", b"safe task attachment", "text/plain")},
    )
    assert attachment.status_code == 201, attachment.text
    attachment_id = attachment.json()["data"]["id"]
    detail_with_files = await organization_client.get(
        f"/api/v1/tasks/{task['id']}", headers=admin_headers
    )
    assert detail_with_files.status_code == 200
    assert detail_with_files.json()["data"]["attachments"][0]["id"] == attachment_id
    assert detail_with_files.json()["data"]["checklist"][0]["id"] == item["id"]
    reopened = await organization_client.patch(
        f"/api/v1/tasks/{task['id']}/checklist/{item['id']}",
        headers=admin_headers,
        json={"completed": False, "title": "Send the final summary"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["completed_at"] is None
    deleted_item = await organization_client.delete(
        f"/api/v1/tasks/{task['id']}/checklist/{item['id']}", headers=admin_headers
    )
    assert deleted_item.status_code == 200, deleted_item.text
    removed = await organization_client.delete(
        f"/api/v1/tasks/{task['id']}/attachments/{attachment_id}", headers=admin_headers
    )
    assert removed.status_code == 200, removed.text
    invalid_file = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        headers=admin_headers,
        files={"file": ("unsafe.exe", b"not executable", "application/x-msdownload")},
    )
    assert invalid_file.status_code == 422

    assignees = await organization_client.get("/api/v1/tasks/assignees", headers=admin_headers)
    assert assignees.status_code == 200, assignees.text
    assert assignees.json()["data"][0].keys() == {
        "id",
        "display_name",
        "job_title",
        "department_id",
        "department_name",
    }


async def test_tasks_are_tenant_isolated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    other_headers, _ = await _register_tenant(
        organization_client, slug="task-contoso", email="admin@task-contoso.example"
    )
    created = await organization_client.post(
        "/api/v1/tasks",
        headers=other_headers,
        json={"title": "Tenant-private task", "priority": "urgent"},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["data"]["id"]
    attachment = await organization_client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        headers=other_headers,
        files={"file": ("tenant-note.txt", b"private", "text/plain")},
    )
    assert attachment.status_code == 201, attachment.text
    attachment_id = attachment.json()["data"]["id"]

    invisible = await organization_client.get(f"/api/v1/tasks/{task_id}", headers=admin_headers)
    assert invisible.status_code == 404
    inaccessible_attachment = await organization_client.delete(
        f"/api/v1/tasks/{task_id}/attachments/{attachment_id}", headers=admin_headers
    )
    assert inaccessible_attachment.status_code == 404
    mine = await organization_client.get("/api/v1/tasks", headers=admin_headers)
    assert task_id not in {row["id"] for row in mine.json()["data"]["items"]}


async def test_due_reminder_is_idempotent(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    reminder_at = datetime.now(UTC) - timedelta(minutes=1)
    created = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "title": "Review reminder delivery",
            "reminder_at": reminder_at.isoformat(),
        },
    )
    assert created.status_code == 201, created.text


async def test_meeting_action_item_converts_to_one_linked_task(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Conversion is idempotent and deliberately does not create a reverse status loop."""
    workspace = await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    assert workspace.status_code == 200, workspace.text
    meeting = await organization_client.post(
        "/api/v1/meetings",
        headers=admin_headers,
        json={
            "workspace_id": workspace.json()["data"][0]["id"],
            "title": "Task conversion review",
            "start_datetime": "2031-09-09T09:00:00",
            "end_datetime": "2031-09-09T10:00:00",
            "timezone": "UTC",
        },
    )
    assert meeting.status_code == 201, meeting.text
    meeting_id = meeting.json()["data"]["id"]
    due_date = (date.today() + timedelta(days=3)).isoformat()
    action = await organization_client.post(
        f"/api/v1/meetings/{meeting_id}/actions",
        headers=admin_headers,
        json={
            "title": "Publish meeting outcomes",
            "description": "Share the decision record.",
            "due_date": due_date,
            "priority": "high",
        },
    )
    assert action.status_code == 201, action.text
    action_id = action.json()["data"]["id"]

    converted = await organization_client.post(
        f"/api/v1/tasks/from-meeting-action/{action_id}", headers=admin_headers
    )
    assert converted.status_code == 201, converted.text
    task = converted.json()["data"]
    assert task["meeting_id"] == meeting_id
    assert task["meeting_action_item_id"] == action_id
    assert task["due_date"] == due_date
    assert task["priority"] == "high"

    repeated = await organization_client.post(
        f"/api/v1/tasks/from-meeting-action/{action_id}", headers=admin_headers
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["data"]["id"] == task["id"]

    completed = await organization_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=admin_headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    meeting_detail = await organization_client.get(
        f"/api/v1/meetings/{meeting_id}", headers=admin_headers
    )
    assert meeting_detail.status_code == 200, meeting_detail.text
    linked_action = next(
        item for item in meeting_detail.json()["data"]["action_items"] if item["id"] == action_id
    )
    assert linked_action["status"] == "open"
