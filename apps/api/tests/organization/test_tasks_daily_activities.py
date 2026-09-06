"""Integrated work-management API contract tests."""

import asyncio
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.tasks.service import TaskService
from meetinghq_api.modules.users.models import Role, User
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
    attachment_payload = attachment.json()["data"]
    attachment_id = attachment_payload["id"]
    owner_download = await organization_client.get(attachment_payload["url"], headers=admin_headers)
    assert owner_download.status_code == 200, owner_download.text
    assert owner_download.content == b"safe task attachment"
    path_safe_attachment = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        headers=admin_headers,
        files={"file": ("../../weekly-notes.txt", b"path safe", "text/plain")},
    )
    assert path_safe_attachment.status_code == 201, path_safe_attachment.text
    assert path_safe_attachment.json()["data"]["filename"] == "weekly-notes.txt"
    detail_with_files = await organization_client.get(
        f"/api/v1/tasks/{task['id']}", headers=admin_headers
    )
    assert detail_with_files.status_code == 200
    assert attachment_id in {row["id"] for row in detail_with_files.json()["data"]["attachments"]}
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
    deleted_download = await organization_client.get(
        attachment_payload["url"], headers=admin_headers
    )
    assert deleted_download.status_code == 404
    invalid_attachment = await organization_client.delete(
        f"/api/v1/tasks/{task['id']}/attachments/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert invalid_attachment.status_code == 404
    invalid_file = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        headers=admin_headers,
        files={"file": ("unsafe.exe", b"not executable", "application/x-msdownload")},
    )
    assert invalid_file.status_code == 422
    archived = await organization_client.delete(
        f"/api/v1/tasks/{task['id']}", headers=admin_headers
    )
    assert archived.status_code == 200, archived.text
    archived_upload = await organization_client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        headers=admin_headers,
        files={"file": ("archive.txt", b"not accepted", "text/plain")},
    )
    assert archived_upload.status_code == 404

    assignees = await organization_client.get("/api/v1/tasks/assignees", headers=admin_headers)
    assert assignees.status_code == 200, assignees.text
    assert assignees.json()["data"][0].keys() == {
        "id",
        "display_name",
        "avatar_url",
        "job_title",
        "department_id",
        "department_name",
    }


async def test_tasks_are_tenant_isolated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    other_headers, other_identity = await _register_tenant(
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
    attachment_url = attachment.json()["data"]["url"]
    checklist = await organization_client.post(
        f"/api/v1/tasks/{task_id}/checklist",
        headers=other_headers,
        json={"title": "Private checklist item"},
    )
    assert checklist.status_code == 201, checklist.text
    activity = await organization_client.post(
        "/api/v1/tasks/activities",
        headers=other_headers,
        json={"activity_date": date.today().isoformat(), "summary": "Private work"},
    )
    assert activity.status_code == 201, activity.text

    invisible = await organization_client.get(f"/api/v1/tasks/{task_id}", headers=admin_headers)
    assert invisible.status_code == 404
    forbidden_mutations = [
        organization_client.patch(
            f"/api/v1/tasks/{task_id}", headers=admin_headers, json={"title": "Probe"}
        ),
        organization_client.patch(
            f"/api/v1/tasks/{task_id}", headers=admin_headers, json={"status": "completed"}
        ),
        organization_client.patch(
            f"/api/v1/tasks/{task_id}", headers=admin_headers, json={"status": "not_started"}
        ),
        organization_client.post(
            f"/api/v1/tasks/{task_id}/comments", headers=admin_headers, json={"body": "Probe"}
        ),
        organization_client.patch(
            f"/api/v1/tasks/{task_id}/checklist/{checklist.json()['data']['id']}",
            headers=admin_headers,
            json={"completed": True},
        ),
    ]
    for response in await asyncio.gather(*forbidden_mutations):
        assert response.status_code == 404, response.text
    inaccessible_attachment = await organization_client.delete(
        f"/api/v1/tasks/{task_id}/attachments/{attachment_id}", headers=admin_headers
    )
    assert inaccessible_attachment.status_code == 404
    cross_tenant_download = await organization_client.get(attachment_url, headers=admin_headers)
    assert cross_tenant_download.status_code == 404
    cross_tenant_activity = await organization_client.get(
        f"/api/v1/tasks/activities?user_id={other_identity['user']['id']}", headers=admin_headers
    )
    assert cross_tenant_activity.status_code == 404
    cross_tenant_assignment = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={"title": "Cross-tenant probe", "assignee_id": other_identity["user"]["id"]},
    )
    assert cross_tenant_assignment.status_code == 404
    cross_tenant_filter = await organization_client.get(
        f"/api/v1/tasks?assignee_id={other_identity['user']['id']}", headers=admin_headers
    )
    assert cross_tenant_filter.status_code == 404
    other_workspace = await organization_client.get("/api/v1/workspaces", headers=other_headers)
    assert other_workspace.status_code == 200, other_workspace.text
    other_meeting = await organization_client.post(
        "/api/v1/meetings",
        headers=other_headers,
        json={
            "workspace_id": other_workspace.json()["data"][0]["id"],
            "title": "Tenant-private meeting",
            "start_datetime": "2031-01-01T10:00:00",
            "end_datetime": "2031-01-01T11:00:00",
            "timezone": "UTC",
        },
    )
    assert other_meeting.status_code == 201, other_meeting.text
    other_action = await organization_client.post(
        f"/api/v1/meetings/{other_meeting.json()['data']['id']}/actions",
        headers=other_headers,
        json={"title": "Tenant-private action"},
    )
    assert other_action.status_code == 201, other_action.text
    cross_tenant_meeting_link = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={"title": "Meeting probe", "meeting_id": other_meeting.json()["data"]["id"]},
    )
    assert cross_tenant_meeting_link.status_code == 404
    cross_tenant_action_link = await organization_client.post(
        f"/api/v1/tasks/from-meeting-action/{other_action.json()['data']['id']}",
        headers=admin_headers,
    )
    assert cross_tenant_action_link.status_code == 404
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
    follow_up = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "title": "Review follow-up delivery",
            "follow_up_at": reminder_at.isoformat(),
        },
    )
    assert follow_up.status_code == 201, follow_up.text

    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        actor = await session.scalar(
            select(User)
            .where(User.email == "admin@northstar.example")
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        assert actor is not None
        task_service = TaskService(session, NotificationService(session, get_settings()))
        assert await task_service.process_due_reminders() == 2
        await session.commit()

    async with factory() as session:
        task_service = TaskService(session, NotificationService(session, get_settings()))
        assert await task_service.process_due_reminders() == 0
        await session.commit()

    notifications = await organization_client.get("/api/v1/notifications", headers=admin_headers)
    assert notifications.status_code == 200, notifications.text
    notification_types = {
        row["notification_type"] for row in notifications.json()["data"]["notifications"]
    }
    assert {"task.reminder", "task.follow_up"} <= notification_types


async def test_manager_assignment_is_limited_to_active_direct_reports(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Picker filtering is helpful, but the server is the authorization boundary."""
    workspaces = await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    roles = await organization_client.get("/api/v1/roles", headers=admin_headers)
    assert workspaces.status_code == 200 and roles.status_code == 200
    role_by_name = {role["name"]: role["id"] for role in roles.json()["data"]}

    async def create_employee(
        first_name: str,
        email: str,
        role_name: str,
        manager_id: str | None = None,
    ) -> dict[str, object]:
        response = await organization_client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "first_name": first_name,
                "last_name": "Task acceptance",
                "email": email,
                "workspace_id": workspaces.json()["data"][0]["id"],
                "role_ids": [role_by_name[role_name]],
                "manager_id": manager_id,
                "temporary_password": "TaskAcceptance!123",
                "send_welcome_email": False,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    manager = await create_employee(
        "Task manager", "manager.tasks@northstar.example", "Team Manager"
    )
    direct_report = await create_employee(
        "Direct report",
        "direct.report.tasks@northstar.example",
        "Employee",
        str(manager["id"]),
    )
    unrelated = await create_employee(
        "Unrelated employee", "unrelated.tasks@northstar.example", "Employee"
    )
    terminated = await create_employee(
        "Former employee", "former.tasks@northstar.example", "Employee", str(manager["id"])
    )
    terminated_response = await organization_client.post(
        f"/api/v1/employees/{terminated['id']}/terminate",
        headers=admin_headers,
        json={"effective_date": date.today().isoformat(), "reason": "Acceptance test"},
    )
    assert terminated_response.status_code == 200, terminated_response.text

    manager_login = await organization_client.post(
        "/api/v1/auth/login",
        json={"email": "manager.tasks@northstar.example", "password": "TaskAcceptance!123"},
    )
    assert manager_login.status_code == 200, manager_login.text
    assert "tasks.manage" not in manager_login.json()["data"]["user"]["permissions"]
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['data']['access_token']}"}
    assignees = await organization_client.get("/api/v1/tasks/assignees", headers=manager_headers)
    assert assignees.status_code == 200, assignees.text
    assignee_ids = {row["id"] for row in assignees.json()["data"]}
    assert str(manager["id"]) in assignee_ids
    assert str(direct_report["id"]) in assignee_ids
    assert str(unrelated["id"]) not in assignee_ids
    assert str(terminated["id"]) not in assignee_ids

    assigned = await organization_client.post(
        "/api/v1/tasks",
        headers=manager_headers,
        json={"title": "Manager assignment", "assignee_id": direct_report["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["data"]["assignee_id"] == direct_report["id"]
    self_assigned = await organization_client.post(
        "/api/v1/tasks", headers=manager_headers, json={"title": "Manager self task"}
    )
    assert self_assigned.status_code == 201, self_assigned.text
    forbidden = await organization_client.post(
        "/api/v1/tasks",
        headers=manager_headers,
        json={"title": "Unauthorized assignment", "assignee_id": unrelated["id"]},
    )
    assert forbidden.status_code == 403
    terminated_assignment = await organization_client.post(
        "/api/v1/tasks",
        headers=manager_headers,
        json={"title": "Terminated assignment", "assignee_id": terminated["id"]},
    )
    assert terminated_assignment.status_code == 422

    employee_login = await organization_client.post(
        "/api/v1/auth/login",
        json={"email": "direct.report.tasks@northstar.example", "password": "TaskAcceptance!123"},
    )
    assert employee_login.status_code == 200, employee_login.text
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['data']['access_token']}"}
    employee_tasks = await organization_client.get(
        "/api/v1/tasks?scope=assigned", headers=employee_headers
    )
    assert employee_tasks.status_code == 200, employee_tasks.text
    assert assigned.json()["data"]["id"] in {
        item["id"] for item in employee_tasks.json()["data"]["items"]
    }
    employee_attachment = await organization_client.post(
        f"/api/v1/tasks/{assigned.json()['data']['id']}/attachments",
        headers=employee_headers,
        files={"file": ("assignment.txt", b"direct report attachment", "text/plain")},
    )
    assert employee_attachment.status_code == 201, employee_attachment.text
    manager_attachment = await organization_client.get(
        employee_attachment.json()["data"]["url"], headers=manager_headers
    )
    assert manager_attachment.status_code == 200, manager_attachment.text
    unrelated_login = await organization_client.post(
        "/api/v1/auth/login",
        json={"email": "unrelated.tasks@northstar.example", "password": "TaskAcceptance!123"},
    )
    assert unrelated_login.status_code == 200, unrelated_login.text
    unrelated_attachment = await organization_client.get(
        employee_attachment.json()["data"]["url"],
        headers={"Authorization": f"Bearer {unrelated_login.json()['data']['access_token']}"},
    )
    assert unrelated_attachment.status_code == 404
    notifications = await organization_client.get("/api/v1/notifications", headers=employee_headers)
    assert notifications.status_code == 200, notifications.text
    assert any(
        item["notification_type"] == "task.assigned"
        for item in notifications.json()["data"]["notifications"]
    )


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
