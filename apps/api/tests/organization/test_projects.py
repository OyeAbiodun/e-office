"""Integrated, tenant-safe Project Management API contract tests."""

from datetime import date, timedelta

from httpx import AsyncClient

from tests.organization.test_tenant_isolation import _register_tenant


async def _identity(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    me = await client.get("/api/v1/auth/me", headers=headers)
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    assert me.status_code == 200 and workspaces.status_code == 200
    return me.json()["data"]["id"], workspaces.json()["data"][0]["id"]


async def test_project_lifecycle_work_and_reporting_are_integrated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    user_id, workspace_id = await _identity(organization_client, admin_headers)
    today = date.today()
    created = await organization_client.post(
        "/api/v1/projects",
        headers=admin_headers,
        json={
            "name": "Customer portal rollout",
            "description": "Coordinate the production rollout.",
            "project_manager_id": user_id,
            "start_date": today.isoformat(),
            "target_end_date": (today + timedelta(days=30)).isoformat(),
            "priority": "high",
        },
    )
    assert created.status_code == 201, created.text
    project = created.json()["data"]
    assert project["project_code"].startswith("PRJ-")
    assert project["member_count"] == 1

    listed = await organization_client.get(
        "/api/v1/projects", headers=admin_headers, params={"search": "portal", "page_size": 10}
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 1

    milestone_response = await organization_client.post(
        f"/api/v1/projects/{project['id']}/milestones",
        headers=admin_headers,
        json={
            "name": "Production readiness",
            "owner_id": user_id,
            "target_date": (today + timedelta(days=14)).isoformat(),
        },
    )
    assert milestone_response.status_code == 201, milestone_response.text
    milestone = milestone_response.json()["data"]

    task_response = await organization_client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=admin_headers,
        json={
            "title": "Complete rollout checklist",
            "assignee_id": user_id,
            "milestone_id": milestone["id"],
            "due_date": (today + timedelta(days=7)).isoformat(),
        },
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()["data"]
    assert task["project_id"] == project["id"]
    assert task["milestone_id"] == milestone["id"]

    standalone = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={"title": "Existing project candidate", "assignee_id": user_id},
    )
    assert standalone.status_code == 201, standalone.text
    standalone_id = standalone.json()["data"]["id"]
    linked = await organization_client.put(
        f"/api/v1/projects/{project['id']}/tasks/{standalone_id}", headers=admin_headers
    )
    repeated_link = await organization_client.put(
        f"/api/v1/projects/{project['id']}/tasks/{standalone_id}", headers=admin_headers
    )
    assert linked.status_code == 200 and repeated_link.status_code == 200
    unlinked = await organization_client.delete(
        f"/api/v1/projects/{project['id']}/tasks/{standalone_id}", headers=admin_headers
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["data"]["project_id"] is None

    activity = await organization_client.post(
        "/api/v1/tasks/activities",
        headers=admin_headers,
        json={
            "activity_date": today.isoformat(),
            "summary": "Validated production rollout dependencies.",
            "task_id": task["id"],
            "project_id": project["id"],
            "duration_minutes": 45,
        },
    )
    assert activity.status_code == 201, activity.text
    assert activity.json()["data"]["project_id"] == project["id"]

    completed_task = await organization_client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=admin_headers,
        json={"status": "completed"},
    )
    assert completed_task.status_code == 200, completed_task.text
    project_detail = await organization_client.get(
        f"/api/v1/projects/{project['id']}", headers=admin_headers
    )
    assert project_detail.status_code == 200, project_detail.text
    assert project_detail.json()["data"]["project"]["progress"] == 100
    assert "project.task_completed" in {
        row["event_type"] for row in project_detail.json()["data"]["activity"]
    }

    meeting = await organization_client.post(
        "/api/v1/meetings",
        headers=admin_headers,
        json={
            "workspace_id": workspace_id,
            "project_id": project["id"],
            "title": "Rollout review",
            "start_datetime": "2027-10-04T09:00:00Z",
            "end_datetime": "2027-10-04T10:00:00Z",
            "timezone": "UTC",
        },
    )
    assert meeting.status_code == 201, meeting.text
    assert meeting.json()["data"]["project_id"] == project["id"]

    update = await organization_client.post(
        f"/api/v1/projects/{project['id']}/updates",
        headers=admin_headers,
        json={
            "reporting_date": today.isoformat(),
            "summary": "Rollout remains on track.",
            "accomplishments": "Production checklist started.",
            "next_steps": "Complete verification.",
        },
    )
    assert update.status_code == 201, update.text

    risk = await organization_client.post(
        f"/api/v1/projects/{project['id']}/risks",
        headers=admin_headers,
        json={"title": "Provider delay", "severity": "high", "owner_id": user_id},
    )
    assert risk.status_code == 201, risk.text
    closed_risk = await organization_client.patch(
        f"/api/v1/projects/{project['id']}/risks/{risk.json()['data']['id']}",
        headers=admin_headers,
        json={"status": "closed", "mitigation": "Fallback provider verified."},
    )
    assert closed_risk.status_code == 200, closed_risk.text

    issue = await organization_client.post(
        f"/api/v1/projects/{project['id']}/issues",
        headers=admin_headers,
        json={"title": "Missing approval", "severity": "critical", "owner_id": user_id},
    )
    assert issue.status_code == 201, issue.text
    no_resolution = await organization_client.patch(
        f"/api/v1/projects/{project['id']}/issues/{issue.json()['data']['id']}",
        headers=admin_headers,
        json={"status": "resolved"},
    )
    assert no_resolution.status_code == 422
    resolved = await organization_client.patch(
        f"/api/v1/projects/{project['id']}/issues/{issue.json()['data']['id']}",
        headers=admin_headers,
        json={"status": "resolved", "resolution": "Approval recorded."},
    )
    assert resolved.status_code == 200, resolved.text

    report = await organization_client.get(
        f"/api/v1/projects/{project['id']}/report",
        headers=admin_headers,
        params={
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
        },
    )
    assert report.status_code == 200, report.text
    report_data = report.json()["data"]
    assert report_data["activities"][0]["summary"].startswith("Validated")
    assert report_data["updates"][0]["summary"] == "Rollout remains on track."

    by_date = await organization_client.get(
        "/api/v1/projects",
        headers=admin_headers,
        params={
            "target_from": (today + timedelta(days=20)).isoformat(),
            "target_to": (today + timedelta(days=40)).isoformat(),
            "page_size": 10,
        },
    )
    assert by_date.status_code == 200, by_date.text
    assert project["id"] in {row["id"] for row in by_date.json()["data"]["items"]}

    for target in ("planned", "active"):
        transitioned = await organization_client.patch(
            f"/api/v1/projects/{project['id']}",
            headers=admin_headers,
            json={"status": target},
        )
        assert transitioned.status_code == 200, transitioned.text
    guarded_completion = await organization_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=admin_headers,
        json={"status": "completed"},
    )
    assert guarded_completion.status_code == 409
    completed = await organization_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=admin_headers,
        json={"status": "completed", "completion_override": True},
    )
    assert completed.status_code == 200, completed.text
    archived = await organization_client.post(
        f"/api/v1/projects/{project['id']}/archive", headers=admin_headers
    )
    assert archived.status_code == 200, archived.text
    read_only = await organization_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=admin_headers,
        json={"name": "Should not change"},
    )
    assert read_only.status_code == 409


async def test_project_manager_transfer_updates_membership_roles(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    admin_id, workspace_id = await _identity(organization_client, admin_headers)
    roles = await organization_client.get("/api/v1/roles", headers=admin_headers)
    role_id = next(row["id"] for row in roles.json()["data"] if row["name"] == "Employee")
    employee = await organization_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Priya",
            "last_name": "Manager",
            "email": "priya.project@northstar.example",
            "workspace_id": workspace_id,
            "role_ids": [role_id],
            "temporary_password": "ProjectAcceptance!123",
            "send_welcome_email": False,
        },
    )
    assert employee.status_code == 201, employee.text
    employee_id = employee.json()["data"]["id"]
    created = await organization_client.post(
        "/api/v1/projects",
        headers=admin_headers,
        json={"name": "Manager transfer", "project_manager_id": admin_id},
    )
    project_id = created.json()["data"]["id"]
    transferred = await organization_client.patch(
        f"/api/v1/projects/{project_id}",
        headers=admin_headers,
        json={"project_manager_id": employee_id},
    )
    assert transferred.status_code == 200, transferred.text
    detail = await organization_client.get(f"/api/v1/projects/{project_id}", headers=admin_headers)
    roles_by_user = {row["user_id"]: row["role"] for row in detail.json()["data"]["members"]}
    assert roles_by_user[employee_id] == "project_manager"
    assert roles_by_user[admin_id] == "project_lead"


async def test_projects_and_secure_files_are_tenant_isolated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    admin_id, workspace_id = await _identity(organization_client, admin_headers)
    other_headers, other_identity = await _register_tenant(
        organization_client, slug="project-contoso", email="admin@project-contoso.example"
    )
    other_user_id = other_identity["user"]["id"]  # type: ignore[index]
    created = await organization_client.post(
        "/api/v1/projects",
        headers=other_headers,
        json={"name": "Contoso confidential", "project_manager_id": other_user_id},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    attachment = await organization_client.post(
        f"/api/v1/projects/{project_id}/attachments",
        headers=other_headers,
        files={"file": ("project-plan.txt", b"tenant private", "text/plain")},
    )
    assert attachment.status_code == 201, attachment.text
    attachment_id = attachment.json()["data"]["id"]
    assert "url" not in attachment.json()["data"]
    owner_download = await organization_client.get(
        f"/api/v1/projects/{project_id}/attachments/{attachment_id}/download",
        headers=other_headers,
    )
    assert owner_download.status_code == 200
    assert owner_download.content == b"tenant private"

    for method, path, body in (
        ("get", f"/api/v1/projects/{project_id}", None),
        ("patch", f"/api/v1/projects/{project_id}", {"name": "Tenant probe"}),
        (
            "get",
            f"/api/v1/projects/{project_id}/attachments/{attachment_id}/download",
            None,
        ),
    ):
        response = await organization_client.request(method, path, headers=admin_headers, json=body)
        assert response.status_code == 404, response.text
        assert "Contoso" not in response.text

    nested_probes = (
        (
            "post",
            f"/api/v1/projects/{project_id}/members",
            {"user_id": admin_id, "role": "member"},
            None,
        ),
        (
            "post",
            f"/api/v1/projects/{project_id}/milestones",
            {"name": "Tenant probe milestone"},
            None,
        ),
        ("get", f"/api/v1/projects/{project_id}/tasks", None, None),
        (
            "post",
            f"/api/v1/projects/{project_id}/updates",
            {"reporting_date": date.today().isoformat(), "summary": "Tenant probe"},
            None,
        ),
        (
            "post",
            f"/api/v1/projects/{project_id}/risks",
            {"title": "Tenant probe risk"},
            None,
        ),
        (
            "post",
            f"/api/v1/projects/{project_id}/issues",
            {"title": "Tenant probe issue"},
            None,
        ),
        (
            "get",
            f"/api/v1/projects/{project_id}/report",
            None,
            {
                "start_date": (date.today() - timedelta(days=1)).isoformat(),
                "end_date": date.today().isoformat(),
            },
        ),
        (
            "post",
            "/api/v1/meetings",
            {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "title": "Tenant probe meeting",
                "start_datetime": "2027-10-04T09:00:00Z",
                "end_datetime": "2027-10-04T10:00:00Z",
                "timezone": "UTC",
            },
            None,
        ),
    )
    for method, path, body, params in nested_probes:
        response = await organization_client.request(
            method, path, headers=admin_headers, json=body, params=params
        )
        assert response.status_code == 404, response.text
        assert "Contoso" not in response.text

    visible = await organization_client.get("/api/v1/projects", headers=admin_headers)
    assert visible.status_code == 200, visible.text
    assert project_id not in {row["id"] for row in visible.json()["data"]["items"]}
