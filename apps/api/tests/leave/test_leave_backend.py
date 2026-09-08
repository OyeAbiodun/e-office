"""Core Leave policy, workflow, privacy, and idempotency regressions."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.calendar.models import Calendar, CalendarEvent, CalendarType, Holiday
from meetinghq_api.modules.leave.models import (
    LeaveBalanceLedgerEntry,
)
from meetinghq_api.modules.notifications.email_templates import (
    EmailTemplateRegistry,
    LeaveEmailData,
    TemplateKey,
)
from meetinghq_api.modules.notifications.models import Notification
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import Role, User, UserStatus


async def _register_tenant(
    client: AsyncClient, *, slug: str, email: str
) -> tuple[dict[str, str], dict[str, object]]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": slug.title(),
            "organization_slug": slug,
            "workspace_name": f"{slug.title()} HQ",
            "email": email,
            "username": f"{slug}.admin",
            "first_name": slug.title(),
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert response.status_code == 201, response.text
    payload: dict[str, object] = response.json()["data"]
    token = payload["access_token"]
    assert isinstance(token, str)
    return {"Authorization": f"Bearer {token}"}, payload


async def _admin_id(client: AsyncClient) -> str:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        user = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert user
        return str(user.id)


async def _foundation(
    client: AsyncClient, headers: dict[str, str]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    leave_type = (
        await client.post(
            "/api/v1/leave/types",
            headers=headers,
            json={
                "name": "Annual Leave",
                "code": "annual",
                "default_entitlement": "20",
                "half_day_supported": True,
            },
        )
    ).json()["data"]
    period = (
        await client.post(
            "/api/v1/leave/periods",
            headers=headers,
            json={
                "name": "FY 2026",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "status": "open",
            },
        )
    ).json()["data"]
    employee_id = await _admin_id(client)
    entitlement_response = await client.post(
        "/api/v1/leave/entitlements",
        headers=headers,
        json={
            "employee_id": employee_id,
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "20",
            "reason": "Annual allocation",
        },
    )
    assert entitlement_response.status_code == 201, entitlement_response.text
    return leave_type, period, entitlement_response.json()["data"]


async def _employee_identity(
    client: AsyncClient,
    *,
    name: str = "employee",
    manager_id: uuid.UUID | None = None,
    employment_type: str = "permanent",
    employment_status: str = "active",
) -> tuple[dict[str, str], uuid.UUID]:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert admin
        role = await session.scalar(
            select(Role).where(
                Role.organization_id == admin.organization_id, Role.name == "Employee"
            )
        )
        assert role
        actor = User(
            organization_id=admin.organization_id,
            email=f"{name}@northstar.example",
            username=name,
            first_name=name.title(),
            last_name="Example",
            display_name=f"{name.title()} Example",
            password_hash="unused-fixture",  # noqa: S106 - no interactive login
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=[role],
            manager_id=manager_id,
            employment_type=employment_type,
            employment_status=employment_status,
            employee_number=f"NS-{name.upper()}",
        )
        session.add(actor)
        await session.flush()
        token = AccessTokenService(get_settings()).create(
            actor.id, actor.organization_id, {permission.name for permission in role.permissions}
        )
        actor_id = actor.id
        await session.commit()
    return {"Authorization": f"Bearer {token}"}, actor_id


async def test_leave_type_period_entitlement_and_balances(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    leave_type, period, entitlement = await _foundation(organization_client, admin_headers)
    assert leave_type["code"] == "ANNUAL"
    assert period["status"] == "open"
    response = await organization_client.get("/api/v1/leave/my/balances", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"][0]["available"] == "20.00"
    admin = await organization_client.get("/api/v1/leave/balances", headers=admin_headers)
    assert admin.status_code == 200
    assert admin.json()["data"]["items"][0]["entitlement_id"] == entitlement["id"]


async def test_request_pending_reservation_and_duplicate_submit(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    leave_type, _period, entitlement = await _foundation(organization_client, admin_headers)
    draft = await organization_client.post(
        "/api/v1/leave/requests",
        headers=admin_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-09-14",
            "end_date": "2026-09-15",
            "reason": "Personal",
        },
    )
    assert draft.status_code == 201, draft.text
    request_id = draft.json()["data"]["id"]
    submitted = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/submit", headers=admin_headers
    )
    assert submitted.status_code == 200, submitted.text
    duplicate = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/submit", headers=admin_headers
    )
    assert duplicate.status_code == 422
    balance = await organization_client.get(
        f"/api/v1/leave/balances/{entitlement['id']}", headers=admin_headers
    )
    assert balance.json()["data"]["pending"] == "2.00"


async def test_working_days_excludes_weekend_and_supports_half_day(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await organization_client.post(
        "/api/v1/leave/working-days",
        headers=admin_headers,
        json={"start_date": "2026-09-11", "end_date": "2026-09-14"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == {
        "calendar_span": 4,
        "excluded_non_working_days": 2,
        "excluded_holidays": 0,
        "chargeable_days": "2",
    }
    half = await organization_client.post(
        "/api/v1/leave/working-days",
        headers=admin_headers,
        json={"start_date": "2026-09-14", "end_date": "2026-09-14", "half_day": True},
    )
    assert half.json()["data"]["chargeable_days"] == "0.5"


def test_leave_email_templates_are_multipart_ready() -> None:
    data = LeaveEmailData(
        "https://app.meetinghq.example/leave/requests/example",
        "Nora Admin",
        "Annual Leave",
        "Sep 14–15, 2026",
        "2",
    )
    keys: tuple[TemplateKey, ...] = (
        "leave.submitted",
        "leave.approved",
        "leave.rejected",
        "leave.withdrawn",
        "leave.cancelled",
    )
    for key in keys:
        rendered = EmailTemplateRegistry.render(key, data)
        assert rendered.key == key
        assert "View leave request" in rendered.html
        assert "View leave request:" in rendered.text


async def test_accrual_idempotency(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        actor = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert actor
        actor_id = actor.id
    leave_type = (
        await organization_client.post(
            "/api/v1/leave/types",
            headers=admin_headers,
            json={
                "name": "Monthly Leave",
                "code": "monthly",
                "default_entitlement": "12",
                "accrual_enabled": True,
                "accrual_frequency": "monthly",
            },
        )
    ).json()["data"]
    period = (
        await organization_client.post(
            "/api/v1/leave/periods",
            headers=admin_headers,
            json={
                "name": "FY 2027",
                "start_date": "2027-01-01",
                "end_date": "2027-12-31",
                "status": "open",
            },
        )
    ).json()["data"]
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(actor_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "0",
        },
    )
    from meetinghq_api.modules.leave.service import LeaveService

    async with factory() as session:
        actor = await session.get(User, actor_id)
        assert actor
        service = LeaveService(session)
        assert await service.process_accruals(actor, date(2027, 1, 31)) == 1
        assert await service.process_accruals(actor, date(2027, 1, 31)) == 0
        row = await session.scalar(
            select(LeaveBalanceLedgerEntry).where(LeaveBalanceLedgerEntry.entry_type == "accrual")
        )
        await session.commit()
        assert row is not None


async def test_leave_type_search_activation_and_period_lifecycle(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    leave_type, period, _entitlement = await _foundation(organization_client, admin_headers)
    search = await organization_client.get(
        "/api/v1/leave/types", headers=admin_headers, params={"search": "annual"}
    )
    assert [item["id"] for item in search.json()["data"]] == [leave_type["id"]]
    deactivated = await organization_client.patch(
        f"/api/v1/leave/types/{leave_type['id']}/active",
        headers=admin_headers,
        params={"active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False
    current = await organization_client.get(
        "/api/v1/leave/periods/current",
        headers=admin_headers,
        params={"on_date": "2026-09-08"},
    )
    assert current.json()["data"]["id"] == period["id"]
    closed = await organization_client.patch(
        f"/api/v1/leave/periods/{period['id']}/status",
        headers=admin_headers,
        json={"status": "closed"},
    )
    assert closed.json()["data"]["status"] == "closed"
    reopened = await organization_client.patch(
        f"/api/v1/leave/periods/{period['id']}/status",
        headers=admin_headers,
        json={"status": "open"},
    )
    assert reopened.json()["data"]["status"] == "open"


async def test_controlled_adjustment_and_immutable_ledger(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    leave_type, period, entitlement = await _foundation(organization_client, admin_headers)
    employee_id = await _admin_id(organization_client)
    response = await organization_client.post(
        "/api/v1/leave/adjustments",
        headers=admin_headers,
        json={
            "employee_id": employee_id,
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "operation": "deduct",
            "amount": "2.5",
            "effective_date": "2026-09-08",
            "reason": "Approved correction",
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()["data"]
    assert result["previous_balance"]["available"] == "20.00"
    assert Decimal(result["adjustment"]["amount"]) == Decimal("-2.50")
    assert result["resulting_balance"]["available"] == "17.50"
    ledger = await organization_client.get(
        "/api/v1/leave/ledger",
        headers=admin_headers,
        params={"employee_id": employee_id, "leave_type_id": str(leave_type["id"])},
    )
    assert ledger.status_code == 200
    assert ledger.json()["data"]["total"] == 2
    assert {row["entry_type"] for row in ledger.json()["data"]["items"]} == {
        "allocation",
        "adjustment",
    }
    filtered = await organization_client.get(
        "/api/v1/leave/balances",
        headers=admin_headers,
        params={"employee_id": employee_id, "leave_period_id": str(period["id"])},
    )
    assert filtered.json()["data"]["items"][0]["available"] == "17.50"
    assert filtered.json()["data"]["total"] == 1


async def test_configurable_working_week_and_holiday_exclusion(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert admin
        session.add(
            Holiday(
                organization_id=admin.organization_id, name="Founders Day", date=date(2026, 9, 14)
            )
        )
        await session.commit()
    configured = await organization_client.put(
        "/api/v1/leave/policy/working-week",
        headers=admin_headers,
        json={"weekdays": [0, 1, 2, 3, 4, 5], "exclude_holidays": True},
    )
    assert configured.status_code == 200
    preview = await organization_client.post(
        "/api/v1/leave/working-days",
        headers=admin_headers,
        json={"start_date": "2026-09-12", "end_date": "2026-09-14"},
    )
    assert preview.json()["data"] == {
        "calendar_span": 3,
        "excluded_non_working_days": 1,
        "excluded_holidays": 1,
        "chargeable_days": "1",
    }


async def test_employee_manager_lifecycle_calendar_notifications_and_summaries(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    manager_id = uuid.UUID(await _admin_id(organization_client))
    employee_headers, employee_id = await _employee_identity(
        organization_client, manager_id=manager_id
    )
    leave_type, period, _ = await _foundation(organization_client, admin_headers)
    entitlement = await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(employee_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "12",
        },
    )
    assert entitlement.status_code == 201
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.get(User, manager_id)
        assert admin
        session.add(
            Calendar(
                organization_id=admin.organization_id,
                owner_id=employee_id,
                name="Employee calendar",
                type=CalendarType.PERSONAL,
                timezone="UTC",
                is_default=True,
            )
        )
        await session.commit()
    draft = await organization_client.post(
        "/api/v1/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-09-21",
            "end_date": "2026-09-22",
            "reason": "Private family matter",
        },
    )
    request_id = draft.json()["data"]["id"]
    assert (
        await organization_client.post(
            f"/api/v1/leave/requests/{request_id}/submit", headers=employee_headers
        )
    ).status_code == 200
    pending = await organization_client.get(
        "/api/v1/leave/requests", headers=admin_headers, params={"scope": "pending"}
    )
    assert pending.json()["data"]["total"] == 1
    assert pending.json()["data"]["items"][0]["employee_name"] == "Employee Example"
    detail = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}", headers=admin_headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["reason"] == "Private family matter"
    approved = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=admin_headers,
        json={"comment": "Approved"},
    )
    assert approved.status_code == 200, approved.text
    duplicate = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=admin_headers,
        json={"comment": "Again"},
    )
    assert duplicate.status_code == 422
    employee_summary = await organization_client.get(
        "/api/v1/leave/my/summary", headers=employee_headers
    )
    assert employee_summary.status_code == 200
    assert employee_summary.json()["data"]["upcoming_approved"][0]["id"] == request_id
    manager_summary = await organization_client.get(
        "/api/v1/leave/team/summary", headers=admin_headers
    )
    assert manager_summary.status_code == 200
    async with factory() as session:
        event = await session.scalar(select(CalendarEvent).where(CalendarEvent.title == "Away"))
        notifications = list((await session.scalars(select(Notification))).all())
        delivery_events = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.resource == "leave",
                        AuditLog.action.in_(
                            ("leave.delivery.local_outbox", "leave.delivery.accepted")
                        ),
                    )
                )
            ).all()
        )
        assert event and event.description is None
        assert len(notifications) >= 2
        assert {row.audit_metadata["template_key"] for row in delivery_events} >= {
            "leave.submitted",
            "leave.approved",
        }
    cancelled = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/cancel",
        headers=employee_headers,
        json={"comment": "Plans changed"},
    )
    assert cancelled.status_code == 200, cancelled.text
    balance = await organization_client.get(
        f"/api/v1/leave/balances/{entitlement.json()['data']['id']}", headers=employee_headers
    )
    assert balance.json()["data"]["used"] == "0.00"


async def test_required_secure_attachments_and_withdrawal(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    manager_id = uuid.UUID(await _admin_id(organization_client))
    employee_headers, employee_id = await _employee_identity(
        organization_client, name="documented", manager_id=manager_id
    )
    leave_type = (
        await organization_client.post(
            "/api/v1/leave/types",
            headers=admin_headers,
            json={
                "name": "Documented Leave",
                "code": "DOC",
                "default_entitlement": "5",
                "attachment_required": True,
            },
        )
    ).json()["data"]
    period = (
        await organization_client.post(
            "/api/v1/leave/periods",
            headers=admin_headers,
            json={"name": "FY 2026", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
    ).json()["data"]
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(employee_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "5",
        },
    )
    request = await organization_client.post(
        "/api/v1/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-10-05",
            "end_date": "2026-10-05",
        },
    )
    request_id = request.json()["data"]["id"]
    blocked = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/submit", headers=employee_headers
    )
    assert blocked.status_code == 422
    invalid = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/attachments",
        headers=employee_headers,
        files={"file": ("unsafe.exe", b"MZ", "application/x-msdownload")},
    )
    assert invalid.status_code == 422
    uploaded = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/attachments",
        headers=employee_headers,
        files={"file": ("evidence.txt", b"supporting evidence", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["data"]["id"]
    listing = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}/attachments", headers=employee_headers
    )
    assert [item["id"] for item in listing.json()["data"]] == [attachment_id]
    downloaded = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}/attachments/{attachment_id}/download",
        headers=employee_headers,
    )
    assert downloaded.content == b"supporting evidence"
    assert (
        await organization_client.post(
            f"/api/v1/leave/requests/{request_id}/submit", headers=employee_headers
        )
    ).status_code == 200
    withdrawn = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/withdraw", headers=employee_headers
    )
    assert withdrawn.status_code == 200


async def test_reports_exports_and_privacy_safe_team_availability(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _foundation(organization_client, admin_headers)
    usage = await organization_client.get(
        "/api/v1/leave/reports/usage", headers=admin_headers, params={"group_by": "leave_type"}
    )
    status = await organization_client.get(
        "/api/v1/leave/reports/status", headers=admin_headers, params={"category": "pending"}
    )
    balances = await organization_client.get(
        "/api/v1/leave/exports/balances.csv", headers=admin_headers
    )
    requests = await organization_client.get(
        "/api/v1/leave/exports/requests.csv", headers=admin_headers
    )
    usage_csv = await organization_client.get(
        "/api/v1/leave/exports/usage.csv", headers=admin_headers
    )
    assert usage.status_code == status.status_code == 200
    assert balances.status_code == requests.status_code == usage_csv.status_code == 200
    assert "employee_number" in balances.text
    assert "request_id" in requests.text
    assert "request_count" in usage_csv.text
    availability = await organization_client.get(
        "/api/v1/leave/team/availability",
        headers=admin_headers,
        params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert "reason" not in availability.text.lower()


async def test_leave_resources_are_undiscoverable_across_tenants(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    _type, period, entitlement = await _foundation(organization_client, admin_headers)
    other_headers, _identity = await _register_tenant(
        organization_client, slug="leave-contoso", email="leave-admin@contoso.example"
    )
    request = await organization_client.get(
        f"/api/v1/leave/balances/{entitlement['id']}", headers=other_headers
    )
    history = await organization_client.get(
        "/api/v1/leave/ledger",
        headers=other_headers,
        params={"leave_period_id": str(period["id"])},
    )
    period_probe = await organization_client.get(
        f"/api/v1/leave/periods/{period['id']}", headers=other_headers
    )
    adjustment = await organization_client.post(
        f"/api/v1/leave/balances/{entitlement['id']}/adjustments",
        headers=other_headers,
        json={"operation": "add", "amount": "1", "effective_date": "2026-09-08", "reason": "probe"},
    )
    assert request.status_code == period_probe.status_code == adjustment.status_code == 404
    assert history.status_code == 200
    assert history.json()["data"]["total"] == 0
    foreign_counts = await organization_client.get("/api/v1/leave/balances", headers=other_headers)
    assert foreign_counts.json()["data"]["total"] == 0


async def test_employment_eligibility_and_terminated_employee_restrictions(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    headers, employee_id = await _employee_identity(
        organization_client, name="contractor", employment_type="contractor"
    )
    leave_type = (
        await organization_client.post(
            "/api/v1/leave/types",
            headers=admin_headers,
            json={
                "name": "Permanent Only",
                "code": "PERM",
                "eligible_employment_types": ["permanent"],
            },
        )
    ).json()["data"]
    period = (
        await organization_client.post(
            "/api/v1/leave/periods",
            headers=admin_headers,
            json={"name": "FY 2026", "start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
    ).json()["data"]
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(employee_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "5",
        },
    )
    ineligible = await organization_client.post(
        "/api/v1/leave/requests",
        headers=headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
        },
    )
    assert ineligible.status_code == 422
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        employee = await session.get(User, employee_id)
        assert employee
        employee.employment_type = "permanent"
        employee.employment_status = "terminated"
        await session.commit()
    terminated = await organization_client.post(
        "/api/v1/leave/requests",
        headers=headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
        },
    )
    assert terminated.status_code == 422


async def test_overlap_insufficient_balance_reject_and_private_detail(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    manager_id = uuid.UUID(await _admin_id(organization_client))
    employee_headers, employee_id = await _employee_identity(
        organization_client, name="limited", manager_id=manager_id
    )
    unrelated_headers, _ = await _employee_identity(organization_client, name="unrelated")
    leave_type, period, _ = await _foundation(organization_client, admin_headers)
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(employee_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "2",
        },
    )
    first = await organization_client.post(
        "/api/v1/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-11-09",
            "end_date": "2026-11-10",
            "reason": "Confidential",
        },
    )
    first_id = first.json()["data"]["id"]
    assert (
        await organization_client.post(
            f"/api/v1/leave/requests/{first_id}/submit", headers=employee_headers
        )
    ).status_code == 200
    overlapping = await organization_client.post(
        "/api/v1/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-11-10",
            "end_date": "2026-11-10",
        },
    )
    overlap_id = overlapping.json()["data"]["id"]
    overlap_submit = await organization_client.post(
        f"/api/v1/leave/requests/{overlap_id}/submit", headers=employee_headers
    )
    assert overlap_submit.status_code == 422
    excessive = await organization_client.post(
        "/api/v1/leave/requests",
        headers=employee_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-11-16",
            "end_date": "2026-11-18",
        },
    )
    excessive_submit = await organization_client.post(
        f"/api/v1/leave/requests/{excessive.json()['data']['id']}/submit",
        headers=employee_headers,
    )
    assert excessive_submit.status_code == 422
    private_probe = await organization_client.get(
        f"/api/v1/leave/requests/{first_id}", headers=unrelated_headers
    )
    assert private_probe.status_code == 404
    rejected = await organization_client.post(
        f"/api/v1/leave/requests/{first_id}/reject",
        headers=admin_headers,
        json={"comment": "Coverage unavailable"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"


async def test_attachment_delete_and_cross_user_denial(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    owner_headers, owner_id = await _employee_identity(organization_client, name="attachment-owner")
    unrelated_headers, _ = await _employee_identity(organization_client, name="attachment-outsider")
    leave_type, period, _ = await _foundation(organization_client, admin_headers)
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(owner_id),
            "leave_type_id": leave_type["id"],
            "leave_period_id": period["id"],
            "allocated_days": "5",
        },
    )
    request = await organization_client.post(
        "/api/v1/leave/requests",
        headers=owner_headers,
        json={
            "leave_type_id": leave_type["id"],
            "start_date": "2026-12-01",
            "end_date": "2026-12-01",
        },
    )
    request_id = request.json()["data"]["id"]
    uploaded = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/attachments",
        headers=owner_headers,
        files={"file": ("safe.txt", b"private", "text/plain")},
    )
    attachment_id = uploaded.json()["data"]["id"]
    denied = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}/attachments/{attachment_id}/download",
        headers=unrelated_headers,
    )
    assert denied.status_code in {403, 404}
    deleted = await organization_client.delete(
        f"/api/v1/leave/requests/{request_id}/attachments/{attachment_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    missing = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}/attachments/{attachment_id}/download",
        headers=owner_headers,
    )
    assert missing.status_code == 404


async def test_carryover_expiry_and_scheduler_idempotency(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        actor = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert actor
        actor_id = actor.id
    kind = (
        await organization_client.post(
            "/api/v1/leave/types",
            headers=admin_headers,
            json={
                "name": "Carry Leave",
                "code": "CARRY",
                "carryover_enabled": True,
                "carryover_limit": "5",
                "carryover_expiry_months": 1,
            },
        )
    ).json()["data"]
    source = (
        await organization_client.post(
            "/api/v1/leave/periods",
            headers=admin_headers,
            json={
                "name": "FY 2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "status": "closed",
            },
        )
    ).json()["data"]
    destination = (
        await organization_client.post(
            "/api/v1/leave/periods",
            headers=admin_headers,
            json={
                "name": "FY 2026",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
        )
    ).json()["data"]
    await organization_client.post(
        "/api/v1/leave/entitlements",
        headers=admin_headers,
        json={
            "employee_id": str(actor_id),
            "leave_type_id": kind["id"],
            "leave_period_id": source["id"],
            "allocated_days": "8",
        },
    )
    from meetinghq_api.modules.leave.service import LeaveService

    async with factory() as session:
        actor = await session.get(User, actor_id)
        assert actor
        service = LeaveService(session)
        assert (
            await service.process_carryover(
                actor,
                uuid.UUID(str(source["id"])),
                uuid.UUID(str(destination["id"])),
                date(2026, 1, 1),
            )
            == 1
        )
        assert (
            await service.process_carryover(
                actor,
                uuid.UUID(str(source["id"])),
                uuid.UUID(str(destination["id"])),
                date(2026, 1, 1),
            )
            == 0
        )
        assert await service.process_expiry(actor, date(2026, 2, 1)) == 1
        assert await service.process_expiry(actor, date(2026, 2, 1)) == 0
        await session.commit()


async def test_invalid_pagination_and_period_overlap_are_rejected(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _foundation(organization_client, admin_headers)
    pagination = await organization_client.get(
        "/api/v1/leave/balances", headers=admin_headers, params={"page_size": 9}
    )
    overlap = await organization_client.post(
        "/api/v1/leave/periods",
        headers=admin_headers,
        json={
            "name": "Overlapping",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
        },
    )
    assert pagination.status_code == 422
    assert overlap.status_code == 422


async def test_shared_policy_scheduler_is_tenant_isolated(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del admin_headers
    await _register_tenant(
        organization_client, slug="scheduler-contoso", email="scheduler@contoso.example"
    )
    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    from meetinghq_api.modules.leave.service import LeaveService

    async with factory() as session:
        organizations = list((await session.scalars(select(Organization))).all())
        assert len(organizations) == 2
        failed_tenant = organizations[0].id

        async def isolated_accrual(self: LeaveService, actor: User, effective_date: date) -> int:
            del self, effective_date
            if actor.organization_id == failed_tenant:
                raise RuntimeError("malformed tenant policy")
            return 1

        async def no_expiry(self: LeaveService, actor: User, effective_date: date) -> int:
            del self, actor, effective_date
            return 0

        monkeypatch.setattr(LeaveService, "process_accruals", isolated_accrual)
        monkeypatch.setattr(LeaveService, "process_expiry", no_expiry)
        processed = await LeaveService(session).process_scheduled_policies(date(2026, 9, 8))
        assert processed == 1
