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

    invisible = await organization_client.get(f"/api/v1/tasks/{task_id}", headers=admin_headers)
    assert invisible.status_code == 404
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
