"""Reporting intelligence workflow, scheduling, export, and isolation contracts."""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.reports.models import GeneratedReport, ReportReviewHistory
from meetinghq_api.modules.reports.service import ReportingService
from tests.organization.test_tenant_isolation import _register_tenant


async def _identity(client: AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    me = await client.get("/api/v1/auth/me", headers=headers)
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    assert me.status_code == 200 and workspaces.status_code == 200
    return me.json()["data"]["id"], workspaces.json()["data"][0]["id"]


async def _employee(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    manager_id: str,
    workspace_id: str,
) -> tuple[str, dict[str, str]]:
    roles = await client.get("/api/v1/roles", headers=headers)
    role_id = next(row["id"] for row in roles.json()["data"] if row["name"] == "Employee")
    temporary = "ReportingTemporary!123"
    changed = "ReportingPermanent!456"
    response = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "first_name": "Riley",
            "last_name": "Reporter",
            "email": "riley.reporting@northstar.example",
            "workspace_id": workspace_id,
            "manager_id": manager_id,
            "role_ids": [role_id],
            "temporary_password": temporary,
            "send_welcome_email": False,
        },
    )
    assert response.status_code == 201, response.text
    employee_id = response.json()["data"]["id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "riley.reporting@northstar.example", "password": temporary},
    )
    assert login.status_code == 200, login.text
    temporary_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    rotate = await client.post(
        "/api/v1/auth/change-password",
        headers=temporary_headers,
        json={
            "current_password": temporary,
            "new_password": changed,
            "confirm_new_password": changed,
        },
    )
    assert rotate.status_code == 200, rotate.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "riley.reporting@northstar.example", "password": changed},
    )
    assert login.status_code == 200, login.text
    return employee_id, {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


async def test_generated_report_review_history_exports_and_stable_snapshot(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    admin_id, workspace_id = await _identity(organization_client, admin_headers)
    employee_id, employee_headers = await _employee(
        organization_client,
        admin_headers,
        manager_id=admin_id,
        workspace_id=workspace_id,
    )
    today = date.today()
    task = await organization_client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "title": "Prepare reporting evidence",
            "assignee_id": employee_id,
            "due_date": today.isoformat(),
        },
    )
    assert task.status_code == 201, task.text
    activity = await organization_client.post(
        "/api/v1/tasks/activities",
        headers=employee_headers,
        json={
            "activity_date": today.isoformat(),
            "summary": "Prepared the verified reporting evidence.",
            "task_id": task.json()["data"]["id"],
            "duration_minutes": 45,
        },
    )
    assert activity.status_code == 201, activity.text

    generated = await organization_client.post(
        "/api/v1/reports",
        headers=admin_headers,
        json={
            "report_type": "employee",
            "subject_id": employee_id,
            "period_type": "daily",
            "period_start": today.isoformat(),
            "period_end": today.isoformat(),
        },
    )
    assert generated.status_code == 201, generated.text
    report = generated.json()["data"]
    assert report["status"] == "generated_draft"
    assert report["authoritative_snapshot"]["summary"]["tasks_total"] == 1
    assert report["authoritative_snapshot"]["summary"]["activities"] == 1

    edited = await organization_client.patch(
        f"/api/v1/reports/{report['id']}",
        headers=employee_headers,
        json={"accomplishments": "Evidence completed and independently verified."},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["version"] == 2
    submitted = await organization_client.post(
        f"/api/v1/reports/{report['id']}/submit", headers=employee_headers
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "submitted"
    review_queue = await organization_client.get(
        "/api/v1/reports", headers=admin_headers, params={"status": "pending_review"}
    )
    assert review_queue.status_code == 200
    assert {item["id"] for item in review_queue.json()["data"]["items"]} == {report["id"]}
    returned = await organization_client.post(
        f"/api/v1/reports/{report['id']}/review",
        headers=admin_headers,
        json={"action": "return", "comment": "Add the validation outcome."},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["data"]["status"] == "returned"
    resubmitted = await organization_client.post(
        f"/api/v1/reports/{report['id']}/submit", headers=employee_headers
    )
    assert resubmitted.status_code == 200, resubmitted.text
    accepted = await organization_client.post(
        f"/api/v1/reports/{report['id']}/review",
        headers=admin_headers,
        json={"action": "accept", "comment": "Accepted."},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "final"

    changed_task = await organization_client.patch(
        f"/api/v1/tasks/{task.json()['data']['id']}",
        headers=admin_headers,
        json={"title": "Source title changed after snapshot"},
    )
    assert changed_task.status_code == 200, changed_task.text
    detail = await organization_client.get(
        f"/api/v1/reports/{report['id']}", headers=employee_headers
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["report"]["authoritative_snapshot"]["tasks"][0]["title"] == (
        "Prepare reporting evidence"
    )
    assert len(data["versions"]) >= 2
    assert {item["action"] for item in data["history"]} >= {
        "generated",
        "edited",
        "submitted",
        "returned",
        "finalized",
    }

    for export_format, signature in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        exported = await organization_client.get(
            f"/api/v1/reports/{report['id']}/export",
            headers=employee_headers,
            params={"format": export_format},
        )
        assert exported.status_code == 200, exported.text
        assert exported.content.startswith(signature)
    csv_export = await organization_client.get(
        f"/api/v1/reports/{report['id']}/export",
        headers=employee_headers,
        params={"format": "csv"},
    )
    assert csv_export.status_code == 200
    assert b"Prepare reporting evidence" in csv_export.content


async def test_reporting_policy_scheduler_is_idempotent_and_tenant_isolated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    admin_id, _ = await _identity(organization_client, admin_headers)
    policy = await organization_client.put(
        "/api/v1/reports/policy",
        headers=admin_headers,
        json={
            "daily_enabled": True,
            "weekly_enabled": True,
            "monthly_enabled": True,
            "review_before_send": True,
            "automatic_submit": False,
            "week_start": 0,
            "week_end": 6,
            "generation_time": "18:00:00",
            "submission_deadline_hours": 24,
            "manager_review_required": True,
            "reminder_hours_before": 4,
            "timezone": "UTC",
            "enabled_report_types": ["daily", "weekly", "monthly", "custom"],
        },
    )
    assert policy.status_code == 200, policy.text
    invalid_timezone = await organization_client.put(
        "/api/v1/reports/policy",
        headers=admin_headers,
        json={**policy.json()["data"], "timezone": "Not/A-Timezone"},
    )
    assert invalid_timezone.status_code == 422

    first = await organization_client.post("/api/v1/reports/scheduler/run", headers=admin_headers)
    second = await organization_client.post("/api/v1/reports/scheduler/run", headers=admin_headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["data"]["generated"] >= 1
    assert second.json()["data"]["generated"] == 0

    enabled_auto_submit = await organization_client.put(
        "/api/v1/reports/policy",
        headers=admin_headers,
        json={
            **policy.json()["data"],
            "automatic_submit": True,
            "submission_deadline_hours": 1,
        },
    )
    assert enabled_auto_submit.status_code == 200, enabled_auto_submit.text
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        reporting = ReportingService(session, NotificationService(session, get_settings()))
        processed = await reporting.process_submission_deadlines(
            datetime.now(UTC) + timedelta(days=30)
        )
        assert processed >= 1
        auto_report = await session.scalar(
            select(GeneratedReport).where(GeneratedReport.organization_id.is_not(None))
        )
        assert auto_report is not None
        assert auto_report.status == "final"
        assert auto_report.submission_mode == "automatic"
        automated_history = await session.scalar(
            select(ReportReviewHistory).where(
                ReportReviewHistory.report_id == auto_report.id,
                ReportReviewHistory.action == "final",
                ReportReviewHistory.actor_id.is_(None),
            )
        )
        assert automated_history is not None
        await session.commit()

    reports = await organization_client.get("/api/v1/reports", headers=admin_headers)
    assert reports.status_code == 200
    report_id = reports.json()["data"]["items"][0]["id"]
    other_headers, _ = await _register_tenant(
        organization_client,
        slug="reporting-contoso",
        email="admin@reporting-contoso.example",
    )
    denied = await organization_client.get(f"/api/v1/reports/{report_id}", headers=other_headers)
    assert denied.status_code == 404
    assert "Northstar" not in denied.text
    denied_export = await organization_client.get(
        f"/api/v1/reports/{report_id}/export",
        headers=other_headers,
        params={"format": "csv"},
    )
    assert denied_export.status_code == 404
    assert "Northstar" not in denied_export.text
    foreign_subject = await organization_client.post(
        "/api/v1/reports",
        headers=other_headers,
        json={
            "report_type": "employee",
            "subject_id": admin_id,
            "period_type": "custom",
            "period_start": (date.today() - timedelta(days=1)).isoformat(),
            "period_end": date.today().isoformat(),
        },
    )
    assert foreign_subject.status_code == 404
