"""Payroll lifecycle, Finance posting, privacy, and tenant isolation acceptance."""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.audit.models import AuditLog
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.finance.models import FinanceTransaction
from meetinghq_api.modules.leave.models import LeavePeriod, LeaveRequest, LeaveType
from meetinghq_api.modules.notifications.models import Notification
from meetinghq_api.modules.payroll.models import PayrollLoan, PayrollPayment
from meetinghq_api.modules.users.models import Role, User, UserStatus
from tests.organization.test_tenant_isolation import _register_tenant


async def identity(
    client: AsyncClient,
    name: str,
    role_names: list[str],
    *,
    employee: bool = False,
    employment_start: date | None = None,
    employment_end: date | None = None,
) -> tuple[dict[str, str], uuid.UUID]:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert admin
        roles = list(
            (
                await session.scalars(
                    select(Role).where(
                        Role.organization_id == admin.organization_id,
                        Role.name.in_(role_names),
                    )
                )
            ).all()
        )
        assert {role.name for role in roles} == set(role_names)
        actor = User(
            organization_id=admin.organization_id,
            email=f"{name}@northstar.example",
            username=name,
            first_name=name.title(),
            last_name="Example",
            display_name=f"{name.title()} Example",
            password_hash="unused-payroll-fixture",  # noqa: S106
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=roles,
            employee_number=f"NS-{name.upper()}" if employee else None,
            employment_status="active",
            employment_start_date=employment_start,
            employment_end_date=employment_end,
        )
        session.add(actor)
        await session.flush()
        permissions = {permission.name for role in roles for permission in role.permissions}
        token = AccessTokenService(get_settings()).create(
            actor.id, actor.organization_id, permissions
        )
        actor_id = actor.id
        await session.commit()
    return {"Authorization": f"Bearer {token}"}, actor_id


async def payroll_foundation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    employee_id: uuid.UUID,
) -> tuple[str, str, str]:
    housing = await client.post(
        "/api/v1/payroll/components",
        headers=admin_headers,
        json={
            "code": "HOUSING",
            "name": "Housing Allowance",
            "component_kind": "earning",
            "calculation_type": "fixed",
            "taxable": True,
            "pensionable": True,
            "effective_start": "2026-01-01",
        },
    )
    assert housing.status_code == 201, housing.text
    component_id = housing.json()["data"]["id"]
    updated_component = await client.put(
        f"/api/v1/payroll/components/{component_id}",
        headers=admin_headers,
        json={
            "code": "HOUSING",
            "name": "Housing Allowance",
            "description": "Recurring taxable housing allowance",
            "component_kind": "earning",
            "calculation_type": "fixed",
            "taxable": True,
            "pensionable": True,
            "effective_start": "2026-01-01",
        },
    )
    assert updated_component.status_code == 200, updated_component.text
    for payload in (
        {
            "configuration_type": "paye",
            "name": "PAYE 2026",
            "effective_start": "2026-01-01",
            "rules": {
                "annual_relief_fixed": "0",
                "annual_relief_rate": "0",
                "bands": [{"limit": None, "rate": "10"}],
            },
            "change_reason": "Initial controlled PAYE policy",
        },
        {
            "configuration_type": "pension",
            "name": "Pension 2026",
            "effective_start": "2026-01-01",
            "rules": {"basis": "pensionable", "employee_rate": "8", "employer_rate": "10"},
            "change_reason": "Initial pension policy",
        },
        {
            "configuration_type": "nhf",
            "name": "NHF 2026",
            "effective_start": "2026-01-01",
            "rules": {"basis": "basic", "employee_rate": "2.5"},
            "change_reason": "Initial NHF policy",
        },
        {
            "configuration_type": "payroll_policy",
            "name": "Payroll policy 2026",
            "effective_start": "2026-01-01",
            "rules": {"proration_method": "calendar_days"},
            "change_reason": "Canonical calendar-day policy",
        },
    ):
        response = await client.post(
            "/api/v1/payroll/statutory", headers=admin_headers, json=payload
        )
        assert response.status_code == 201, response.text
    structure_body = {
        "employee_id": str(employee_id),
        "basic_salary": "100000",
        "effective_start": "2026-01-01",
        "change_reason": "Initial employment package",
        "items": [{"component_id": component_id, "amount": "20000"}],
    }
    preview = await client.post(
        "/api/v1/payroll/salary-structures/preview",
        headers=admin_headers,
        json=structure_body,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["gross_pay"] == "120000.00"
    assert preview.json()["data"]["net_pay"] == "95900.00"
    structure = await client.post(
        "/api/v1/payroll/salary-structures",
        headers=admin_headers,
        json=structure_body,
    )
    assert structure.status_code == 201, structure.text
    period = await client.post(
        "/api/v1/payroll/periods",
        headers=admin_headers,
        json={
            "name": "September 2026",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "payment_date": "2026-09-30",
        },
    )
    assert period.status_code == 201, period.text
    account = await client.post(
        "/api/v1/finance/accounts",
        headers=admin_headers,
        json={
            "account_name": "Payroll account",
            "account_code": "PAYROLL-NGN",
            "account_type": "bank",
            "bank_name": "Controlled Bank",
            "account_number": "0123456789",
            "opening_balance": "1000000",
        },
    )
    assert account.status_code == 201, account.text
    return period.json()["data"]["id"], account.json()["data"]["id"], structure.json()["data"]["id"]


async def test_complete_payroll_lifecycle_finance_payslip_and_reversal(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    client = organization_client
    officer, _ = await identity(client, "payroll-officer", ["Payroll Officer"])
    approver, _ = await identity(client, "payroll-approver", ["Payroll Approver"])
    accountant, _ = await identity(client, "payroll-accountant", ["Accountant"])
    employee_headers, employee_id = await identity(
        client,
        "payroll-employee",
        ["Employee"],
        employee=True,
        employment_start=date(2026, 1, 1),
    )
    stranger_headers, _ = await identity(client, "payroll-stranger", ["Employee"], employee=True)
    period_id, account_id, _structure_id = await payroll_foundation(
        client, admin_headers, employee_id
    )
    bonus = {
        "employee_id": str(employee_id),
        "adjustment_type": "bonus",
        "amount": "10000",
        "reason": "Quarterly performance",
        "idempotency_key": "bonus-september-employee",
    }
    created_bonus = await client.post(
        f"/api/v1/payroll/periods/{period_id}/adjustments", headers=officer, json=bonus
    )
    assert created_bonus.status_code == 201, created_bonus.text
    replay_bonus = await client.post(
        f"/api/v1/payroll/periods/{period_id}/adjustments", headers=officer, json=bonus
    )
    assert replay_bonus.json()["data"]["id"] == created_bonus.json()["data"]["id"]
    loan = await client.post(
        "/api/v1/payroll/loans",
        headers=officer,
        json={
            "employee_id": str(employee_id),
            "principal": "20000",
            "start_date": "2026-01-01",
            "repayment_amount": "5000",
            "reason": "Approved salary advance",
        },
    )
    assert loan.status_code == 201, loan.text
    prepared = await client.post(f"/api/v1/payroll/periods/{period_id}/prepare", headers=officer)
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()["data"]["id"]
    detail = await client.get(f"/api/v1/payroll/runs/{run_id}", headers=officer)
    assert detail.status_code == 200, detail.text
    payload = detail.json()["data"]
    assert payload["summary"]["employee_count"] == 2  # employee and explicit stranger employee
    target = next(
        row for row in payload["results"]["items"] if row["employee_id"] == str(employee_id)
    )
    assert target["gross_pay"] == "130000.00"
    assert target["paye"] == "13000.00"
    assert target["pension_employee"] == "9600.00"
    assert target["nhf"] == "2500.00"
    assert target["loan_deductions"] == "5000.00"
    assert target["net_pay"] == "99900.00"
    # A salary-less employee is visible as an exception, never silently skipped.
    assert payload["summary"]["exception_count"] == 1
    blocked_submit = await client.post(f"/api/v1/payroll/runs/{run_id}/submit", headers=officer)
    assert blocked_submit.status_code == 422
    # Removing this fixture from active employment resolves the explicit exception on re-prepare.
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        stranger = await session.scalar(
            select(User).where(User.email == "payroll-stranger@northstar.example")
        )
        assert stranger
        stranger.employment_end_date = date(2026, 8, 31)
        await session.commit()
    prepared_again = await client.post(
        f"/api/v1/payroll/periods/{period_id}/prepare", headers=officer
    )
    assert prepared_again.status_code == 200, prepared_again.text
    assert prepared_again.json()["data"]["version"] == 2
    submitted = await client.post(f"/api/v1/payroll/runs/{run_id}/submit", headers=officer)
    assert submitted.status_code == 200, submitted.text
    returned = await client.post(
        f"/api/v1/payroll/runs/{run_id}/return",
        headers=approver,
        json={"reason": "Confirm the performance bonus"},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["data"]["status"] == "returned"
    assert (
        await client.post(f"/api/v1/payroll/periods/{period_id}/prepare", headers=officer)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/payroll/runs/{run_id}/submit", headers=officer)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/payroll/runs/{run_id}/approve", headers=officer)
    ).status_code == 403
    approved = await client.post(f"/api/v1/payroll/runs/{run_id}/approve", headers=approver)
    assert approved.status_code == 200, approved.text
    payment_body = {
        "account_id": account_id,
        "payment_date": "2026-09-30",
        "payment_reference": "BANK-PAY-SEP-2026",
        "idempotency_key": "september-payroll-posting",
    }
    paid = await client.post(
        f"/api/v1/payroll/runs/{run_id}/pay", headers=accountant, json=payment_body
    )
    assert paid.status_code == 200, paid.text
    replay = await client.post(
        f"/api/v1/payroll/runs/{run_id}/pay", headers=accountant, json=payment_body
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == paid.json()["data"]["id"]
    payslips = await client.get("/api/v1/payroll/my/payslips", headers=employee_headers)
    assert payslips.status_code == 200, payslips.text
    result_id = payslips.json()["data"][0]["id"]
    pdf = await client.get(f"/api/v1/payroll/results/{result_id}/payslip", headers=employee_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert pdf.headers["cache-control"] == "private, no-store"
    assert str(employee_id) not in pdf.content.decode("latin-1", errors="ignore")
    assert (
        await client.get(f"/api/v1/payroll/results/{result_id}/payslip", headers=stranger_headers)
    ).status_code == 404
    report = await client.get(f"/api/v1/payroll/runs/{run_id}/reports", headers=approver)
    assert report.status_code == 200 and report.json()["data"]
    exported = await client.get(f"/api/v1/payroll/runs/{run_id}/export", headers=approver)
    assert exported.status_code == 200 and exported.content.startswith(b"\xef\xbb\xbf")
    other_headers, _ = await _register_tenant(
        client, slug="payroll-other", email="admin@payroll-other.example"
    )
    assert (
        await client.get(f"/api/v1/payroll/runs/{run_id}", headers=other_headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/payroll/results/{result_id}/payslip", headers=other_headers)
    ).status_code == 404
    reversed_response = await client.post(
        f"/api/v1/payroll/runs/{run_id}/reverse",
        headers=accountant,
        json={"reason": "Controlled bank rejection", "idempotency_key": "sep-pay-reversal"},
    )
    assert reversed_response.status_code == 200, reversed_response.text
    async with factory() as session:
        finance = list(
            (
                await session.scalars(
                    select(FinanceTransaction).where(
                        FinanceTransaction.transaction_type.in_(["payroll", "payroll_reversal"])
                    )
                )
            ).all()
        )
        assert len(finance) == 2
        assert {row.direction for row in finance} == {"credit", "debit"}
        loan_row = await session.scalar(
            select(PayrollLoan).where(PayrollLoan.id == uuid.UUID(loan.json()["data"]["id"]))
        )
        assert loan_row and loan_row.outstanding_balance == Decimal("20000.00")
        payments = list((await session.scalars(select(PayrollPayment))).all())
        assert len(payments) == 1 and payments[0].reversed_at
        notifications = set((await session.scalars(select(Notification.notification_type))).all())
        assert {
            "payroll_review_requested",
            "payroll_approved",
            "payslip_available",
        } <= notifications
        audits = set((await session.scalars(select(AuditLog.action))).all())
        assert {
            "payroll.salary_structure.created",
            "payroll.prepared",
            "payroll.approved",
            "payroll.paid",
            "payroll.payment_reversed",
            "payroll.payslip.downloaded",
        } <= audits


async def test_effective_date_overlap_and_foreign_references_are_rejected(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    client = organization_client
    employee_headers, employee_id = await identity(
        client, "effective-employee", ["Employee"], employee=True
    )
    _ = employee_headers
    _period_id, _account_id, _structure_id = await payroll_foundation(
        client, admin_headers, employee_id
    )
    overlap = await client.post(
        "/api/v1/payroll/salary-structures",
        headers=admin_headers,
        json={
            "employee_id": str(employee_id),
            "basic_salary": "110000",
            "effective_start": "2026-06-01",
            "change_reason": "Unsafe overlap",
        },
    )
    assert overlap.status_code == 409
    statutory_overlap = await client.post(
        "/api/v1/payroll/statutory",
        headers=admin_headers,
        json={
            "configuration_type": "nhf",
            "name": "Conflicting NHF",
            "effective_start": "2026-06-01",
            "rules": {"employee_rate": "3"},
            "change_reason": "Should fail",
        },
    )
    assert statutory_overlap.status_code == 409
    other_headers, other = await _register_tenant(
        client, slug="foreign-payroll", email="admin@foreign-payroll.example"
    )
    foreign_user_id = other["user"]["id"]  # type: ignore[index]
    foreign_structure = await client.post(
        "/api/v1/payroll/salary-structures",
        headers=admin_headers,
        json={
            "employee_id": foreign_user_id,
            "basic_salary": "1000",
            "effective_start": "2026-01-01",
            "change_reason": "Cross tenant attempt",
        },
    )
    assert foreign_structure.status_code == 404
    assert (await client.get("/api/v1/payroll/periods", headers=other_headers)).status_code == 200


async def test_new_hire_unpaid_leave_proration_and_self_approval_are_enforced(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    client = organization_client
    dual_headers, dual_id = await identity(
        client, "payroll-dual-control", ["Payroll Officer", "Payroll Approver"]
    )
    _employee_headers, employee_id = await identity(
        client,
        "payroll-new-hire",
        ["Employee"],
        employee=True,
        employment_start=date(2026, 9, 16),
    )
    period_id, _account_id, _structure_id = await payroll_foundation(
        client, admin_headers, employee_id
    )
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        actor = await session.get(User, dual_id)
        assert actor
        leave_type = LeaveType(
            organization_id=actor.organization_id,
            name="Unpaid Leave",
            code="UNPAID-PAYROLL",
            is_paid=False,
        )
        leave_period = LeavePeriod(
            organization_id=actor.organization_id,
            name="Payroll leave 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        session.add_all([leave_type, leave_period])
        await session.flush()
        session.add(
            LeaveRequest(
                organization_id=actor.organization_id,
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                leave_period_id=leave_period.id,
                start_date=date(2026, 9, 20),
                end_date=date(2026, 9, 22),
                duration_days=Decimal("3"),
                status="approved",
            )
        )
        await session.commit()
    prepared = await client.post(
        f"/api/v1/payroll/periods/{period_id}/prepare", headers=dual_headers
    )
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()["data"]["id"]
    detail = await client.get(f"/api/v1/payroll/runs/{run_id}", headers=dual_headers)
    assert detail.status_code == 200, detail.text
    result = detail.json()["data"]["results"]["items"][0]
    assert result["proration_factor"] == "0.400000"
    assert result["gross_pay"] == "48000.00"
    assert result["calculation_snapshot"]["unpaid_leave_days"] == "3.00"
    submitted = await client.post(f"/api/v1/payroll/runs/{run_id}/submit", headers=dual_headers)
    assert submitted.status_code == 200, submitted.text
    self_approval = await client.post(
        f"/api/v1/payroll/runs/{run_id}/approve", headers=dual_headers
    )
    assert self_approval.status_code == 403
    assert "own payroll" in self_approval.text
