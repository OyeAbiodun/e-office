"""PostgreSQL release-gate evidence for configurable leave policy behavior."""

import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.leave.models import LeaveAttachment
from meetinghq_api.modules.storage.local import LocalStorageProvider
from meetinghq_api.modules.users.models import Role, User, UserStatus
from tests.leave.test_leave_backend import _admin_id, _employee_identity


async def _require_postgresql(client: AsyncClient) -> None:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL leave-policy release gate")


async def _policy(client: AsyncClient, headers: dict[str, str], **overrides: object) -> None:
    body: dict[str, object] = {
        "periods_required": True,
        "entitlements_required": True,
        "auto_open_annual_period": False,
        "relief_person_mode": "disabled",
        "approval_workflow": "manager",
        **overrides,
    }
    response = await client.put("/api/v1/leave/policy", headers=headers, json=body)
    assert response.status_code == 200, response.text


async def _leave_type(
    client: AsyncClient, headers: dict[str, str], *, attachment_required: bool = False
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/leave/types",
        headers=headers,
        json={
            "name": f"Annual Leave {uuid.uuid4().hex[:6]}",
            "code": f"A{uuid.uuid4().hex[:7]}",
            "default_entitlement": "21",
            "attachment_required": attachment_required,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


def _future_workday() -> date:
    value = date.today() + timedelta(days=14)
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


async def _open_period(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    year = date.today().year
    response = await client.post(
        "/api/v1/leave/periods",
        headers=headers,
        json={
            "name": f"Annual Leave {year}",
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
            "status": "open",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


async def _entitle(
    client: AsyncClient,
    headers: dict[str, str],
    employee_id: uuid.UUID | str,
    leave_type_id: str,
    period_id: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/leave/entitlements",
        headers=headers,
        json={
            "employee_id": str(employee_id),
            "leave_type_id": leave_type_id,
            "leave_period_id": period_id,
            "allocated_days": "21",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


async def _eligibility(
    client: AsyncClient, headers: dict[str, str], leave_type_id: str
) -> dict[str, Any]:
    target = _future_workday()
    response = await client.get(
        "/api/v1/leave/my/eligibility",
        headers=headers,
        params={
            "leave_type_id": leave_type_id,
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


async def _draft(
    client: AsyncClient,
    headers: dict[str, str],
    leave_type_id: str,
    relief_person_id: uuid.UUID | None = None,
) -> Any:
    target = _future_workday()
    return await client.post(
        "/api/v1/leave/requests",
        headers=headers,
        json={
            "leave_type_id": leave_type_id,
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "reason": "PostgreSQL release-gate request",
            "relief_person_id": str(relief_person_id) if relief_person_id else None,
        },
    )


async def test_postgresql_periods_required_rejects_dates_without_open_period(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _require_postgresql(organization_client)
    await _policy(organization_client, admin_headers, periods_required=True)
    leave_type = await _leave_type(organization_client, admin_headers)
    result = await _eligibility(organization_client, admin_headers, leave_type["id"])
    assert result["eligible"] is False
    assert result["code"] == "no_applicable_period"


async def test_postgresql_periods_optional_creates_annual_period_and_allows_request(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _require_postgresql(organization_client)
    await _policy(
        organization_client,
        admin_headers,
        periods_required=False,
        entitlements_required=False,
    )
    leave_type = await _leave_type(organization_client, admin_headers)
    result = await _eligibility(organization_client, admin_headers, leave_type["id"])
    assert result["eligible"] is True
    draft = await _draft(organization_client, admin_headers, leave_type["id"])
    assert draft.status_code == 201, draft.text
    detail = await organization_client.get(
        f"/api/v1/leave/requests/{draft.json()['data']['id']}", headers=admin_headers
    )
    assert detail.json()["data"]["leave_period_name"].startswith("Annual Leave ")


async def test_postgresql_entitlements_required_reports_no_entitlement(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _require_postgresql(organization_client)
    await _policy(organization_client, admin_headers, entitlements_required=True)
    leave_type = await _leave_type(organization_client, admin_headers)
    await _open_period(organization_client, admin_headers)
    result = await _eligibility(organization_client, admin_headers, leave_type["id"])
    assert result["eligible"] is False
    assert result["code"] == "no_entitlement"


async def test_postgresql_entitlements_optional_allows_submission_without_allocation(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _require_postgresql(organization_client)
    await _policy(organization_client, admin_headers, entitlements_required=False)
    leave_type = await _leave_type(organization_client, admin_headers)
    await _open_period(organization_client, admin_headers)
    assert (await _eligibility(organization_client, admin_headers, leave_type["id"]))[
        "eligible"
    ] is True
    draft = await _draft(organization_client, admin_headers, leave_type["id"])
    submitted = await organization_client.post(
        f"/api/v1/leave/requests/{draft.json()['data']['id']}/submit",
        headers=admin_headers,
    )
    assert submitted.status_code == 200, submitted.text


@pytest.mark.parametrize(
    ("mode", "with_relief", "expected_status"),
    [("disabled", True, 422), ("optional", False, 201), ("required", False, 422)],
)
async def test_postgresql_relief_person_policy_changes_draft_behavior(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    mode: str,
    with_relief: bool,
    expected_status: int,
) -> None:
    await _require_postgresql(organization_client)
    await _policy(
        organization_client,
        admin_headers,
        periods_required=False,
        entitlements_required=False,
        relief_person_mode=mode,
    )
    leave_type = await _leave_type(organization_client, admin_headers)
    _, relief_id = await _employee_identity(organization_client, name=f"relief-{mode}")
    result = await _draft(
        organization_client,
        admin_headers,
        leave_type["id"],
        relief_id if with_relief else None,
    )
    assert result.status_code == expected_status, result.text
    if mode == "optional":
        with_optional_relief = await _draft(
            organization_client, admin_headers, leave_type["id"], relief_id
        )
        assert with_optional_relief.status_code == 201, with_optional_relief.text
    if mode == "required":
        with_required_relief = await _draft(
            organization_client, admin_headers, leave_type["id"], relief_id
        )
        assert with_required_relief.status_code == 201, with_required_relief.text


async def _manager_identity(client: AsyncClient, name: str) -> tuple[dict[str, str], uuid.UUID]:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert admin
        role = await session.scalar(
            select(Role).where(
                Role.organization_id == admin.organization_id, Role.name == "Team Manager"
            )
        )
        assert role
        manager = User(
            organization_id=admin.organization_id,
            email=f"{name}@northstar.example",
            username=name,
            first_name="Morgan",
            last_name="Manager",
            display_name="Morgan Manager",
            password_hash="unused-fixture",  # noqa: S106
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=[role],
            employee_number=f"NS-{name.upper()}",
        )
        session.add(manager)
        await session.flush()
        from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService

        token = AccessTokenService(get_settings()).create(
            manager.id,
            manager.organization_id,
            {permission.name for permission in role.permissions},
        )
        manager_id = manager.id
        await session.commit()
    return {"Authorization": f"Bearer {token}"}, manager_id


async def _submitted_employee_request(
    client: AsyncClient,
    admin_headers: dict[str, str],
    manager_id: uuid.UUID,
) -> tuple[dict[str, str], str]:
    employee_headers, employee_id = await _employee_identity(
        client, name=f"workflow-{uuid.uuid4().hex[:6]}", manager_id=manager_id
    )
    leave_type = await _leave_type(client, admin_headers)
    period = await _open_period(client, admin_headers)
    await _entitle(client, admin_headers, employee_id, leave_type["id"], period["id"])
    draft = await _draft(client, employee_headers, leave_type["id"])
    assert draft.status_code == 201, draft.text
    request_id = draft.json()["data"]["id"]
    submitted = await client.post(
        f"/api/v1/leave/requests/{request_id}/submit", headers=employee_headers
    )
    assert submitted.status_code == 200, submitted.text
    return employee_headers, request_id


@pytest.mark.parametrize("workflow", ["manager", "hr", "manager_then_hr"])
async def test_postgresql_approval_workflow_enforces_actor_and_stage(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    workflow: str,
) -> None:
    await _require_postgresql(organization_client)
    await _policy(organization_client, admin_headers, approval_workflow=workflow)
    manager_headers, manager_id = await _manager_identity(
        organization_client, f"manager-{workflow}"
    )
    _, request_id = await _submitted_employee_request(
        organization_client, admin_headers, manager_id
    )
    path = f"/api/v1/leave/requests/{request_id}/approve"
    if workflow == "hr":
        denied = await organization_client.post(
            path, headers=manager_headers, json={"comment": "Manager attempt"}
        )
        assert denied.status_code == 403, denied.text
        approved = await organization_client.post(
            path, headers=admin_headers, json={"comment": "HR approved"}
        )
        assert approved.json()["data"]["status"] == "approved"
    else:
        first = await organization_client.post(
            path, headers=manager_headers, json={"comment": "Manager approved"}
        )
        assert first.status_code == 200, first.text
        if workflow == "manager":
            assert first.json()["data"]["status"] == "approved"
        else:
            assert first.json()["data"]["status"] == "submitted"
            assert first.json()["data"]["approval_stage"] == "hr"
            final = await organization_client.post(
                path, headers=admin_headers, json={"comment": "HR approved"}
            )
            assert final.json()["data"]["status"] == "approved"


async def test_postgresql_annual_entitlement_21_is_used_by_eligibility(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await _require_postgresql(organization_client)
    await _policy(organization_client, admin_headers)
    leave_type = await _leave_type(organization_client, admin_headers)
    period = await _open_period(organization_client, admin_headers)
    entitlement = await _entitle(
        organization_client,
        admin_headers,
        await _admin_id(organization_client),
        leave_type["id"],
        period["id"],
    )
    balances = await organization_client.get("/api/v1/leave/my/balances", headers=admin_headers)
    visible = next(
        item for item in balances.json()["data"] if item["entitlement_id"] == entitlement["id"]
    )
    assert visible["entitled"] == "21.00"
    assert visible["available"] == "21.00"
    eligibility = await _eligibility(organization_client, admin_headers, leave_type["id"])
    assert eligibility["eligible"] is True
    assert eligibility["code"] is None
    assert eligibility["available_days"] == "21.00"
    assert "No entitlement" not in eligibility["message"]


async def test_postgresql_required_attachment_survives_failure_retry_replace_and_submit(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    await _require_postgresql(organization_client)
    monkeypatch.setattr(get_settings(), "local_storage_path", str(tmp_path))
    await _policy(
        organization_client,
        admin_headers,
        periods_required=False,
        entitlements_required=False,
    )
    leave_type = await _leave_type(organization_client, admin_headers, attachment_required=True)
    draft = await _draft(organization_client, admin_headers, leave_type["id"])
    assert draft.status_code == 201, draft.text
    request_id = draft.json()["data"]["id"]
    submit_path = f"/api/v1/leave/requests/{request_id}/submit"
    assert (await organization_client.post(submit_path, headers=admin_headers)).status_code == 422

    original_put = LocalStorageProvider.put
    calls = 0

    async def fail_once(self: LocalStorageProvider, *args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected storage write failure")
        return await original_put(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(LocalStorageProvider, "put", fail_once)
    with pytest.raises(OSError, match="injected storage write failure"):
        await organization_client.post(
            f"/api/v1/leave/requests/{request_id}/attachments",
            headers=admin_headers,
            files={"file": ("medical-note.pdf", b"first", "application/pdf")},
        )
    reopened = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}", headers=admin_headers
    )
    assert reopened.json()["data"]["status"] == "draft"
    assert reopened.json()["data"]["attachments"] == []

    uploaded = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/attachments",
        headers=admin_headers,
        files={"file": ("medical-note.pdf", b"first", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    original_id = uploaded.json()["data"]["id"]
    reopened = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}", headers=admin_headers
    )
    assert [item["id"] for item in reopened.json()["data"]["attachments"]] == [original_id]

    replacement = await organization_client.post(
        f"/api/v1/leave/requests/{request_id}/attachments",
        headers=admin_headers,
        files={"file": ("replacement.pdf", b"replacement", "application/pdf")},
    )
    replacement_id = replacement.json()["data"]["id"]
    removed = await organization_client.delete(
        f"/api/v1/leave/requests/{request_id}/attachments/{original_id}",
        headers=admin_headers,
    )
    assert removed.status_code == 200, removed.text
    listing = await organization_client.get(
        f"/api/v1/leave/requests/{request_id}/attachments", headers=admin_headers
    )
    assert [item["id"] for item in listing.json()["data"]] == [replacement_id]
    assert (await organization_client.post(submit_path, headers=admin_headers)).status_code == 200

    factory = organization_client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        persisted = list(
            (
                await session.scalars(
                    select(LeaveAttachment).where(
                        LeaveAttachment.leave_request_id == uuid.UUID(request_id)
                    )
                )
            ).all()
        )
        assert [str(item.id) for item in persisted if item.deleted_at is None] == [replacement_id]
        assert [str(item.id) for item in persisted if item.deleted_at is not None] == [original_id]
