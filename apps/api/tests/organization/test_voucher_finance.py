"""Voucher workflow, Decimal statements, secure documents, and SoD regressions."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService
from meetinghq_api.modules.finance.models import FinanceTransaction, VoucherHistory
from meetinghq_api.modules.notifications.models import Notification
from meetinghq_api.modules.users.models import Role, User, UserStatus
from tests.organization.test_tenant_isolation import _register_tenant


async def identity(
    client: AsyncClient, name: str, role_name: str, manager_id: uuid.UUID | None = None
) -> tuple[dict[str, str], uuid.UUID]:
    factory = client._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert admin
        role = await session.scalar(
            select(Role).where(
                Role.organization_id == admin.organization_id, Role.name == role_name
            )
        )
        assert role
        actor = User(
            organization_id=admin.organization_id,
            email=f"{name}@northstar.example",
            username=name,
            first_name=name,
            last_name="Example",
            display_name=f"{name} Example",
            password_hash="unused-fixture",  # noqa: S106 - test identity cannot log in
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=[role],
            manager_id=manager_id,
        )
        session.add(actor)
        await session.flush()
        token = AccessTokenService(get_settings()).create(
            actor.id, actor.organization_id, {p.name for p in role.permissions}
        )
        actor_id = actor.id
        await session.commit()
        return {"Authorization": f"Bearer {token}"}, actor_id


async def create(
    client: AsyncClient, headers: dict[str, str], **extra: object
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/vouchers",
        headers=headers,
        json={
            "title": "Workshop supplies",
            "description": "Reusable acceptance fixture",
            "line_items": [
                {
                    "description": "Materials",
                    "quantity": "2.500",
                    "unit_price": "40.10",
                    "tax_amount": "4.75",
                }
            ],
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


async def test_finance_complete_workflow_and_replay(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    c = organization_client
    manager, manager_id = await identity(c, "manager", "Team Manager")
    staff, _ = await identity(c, "requester", "Employee", manager_id)
    accountant, _ = await identity(c, "accountant", "Accountant")
    auditor, _ = await identity(c, "auditor", "Auditor")
    task = await c.post(
        "/api/v1/tasks",
        headers=staff,
        json={"title": "Prepare workshop reimbursement", "priority": "normal"},
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["data"]["id"]
    v = await create(c, staff, task_id=task_id)
    assert v["task_id"] == task_id
    base = f"/api/v1/vouchers/{v['id']}"
    assert v["requested_amount"] == "105.00"
    edited = await c.patch(base, headers=staff, json={"title": "Updated purpose"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["requested_amount"] == "105.00"
    assert edited.json()["data"]["description"] == "Reusable acceptance fixture"
    assert (await c.get(base, headers=manager)).status_code == 404
    assert (await c.post(base + "/submit", headers=staff)).status_code == 200
    queue = await c.get("/api/v1/vouchers?status=submitted", headers=manager)
    assert queue.json()["data"]["total"] == 1
    assert (await c.post(base + "/approve", headers=staff, json={})).status_code == 403
    approved = await c.post(
        base + "/approve",
        headers=manager,
        json={"approved_amount": "100.00", "comment": "Within budget"},
    )
    assert approved.status_code == 200, approved.text
    account = await c.post(
        "/api/v1/finance/accounts",
        headers=admin_headers,
        json={
            "account_name": "Operating cash",
            "account_code": "OPS",
            "account_type": "cash",
            "opening_balance": "1000.00",
        },
    )
    assert account.status_code == 201, account.text
    payment = {
        "account_id": account.json()["data"]["id"],
        "amount": "40.00",
        "payment_method": "cash",
        "payment_reference": "LOCAL-001",
        "payment_date": "2030-05-01",
        "idempotency_key": "payment-first",
    }
    assert (await c.post(base + "/disburse", headers=manager, json=payment)).status_code == 403
    partial = await c.post(base + "/disburse", headers=accountant, json=payment)
    assert partial.status_code == 200, partial.text
    assert partial.json()["data"]["status"] == "partially_disbursed"
    assert partial.json()["data"]["outstanding_amount"] == "60.00"
    assert (await c.post(base + "/disburse", headers=accountant, json=payment)).status_code == 200
    assert (
        await c.post(base + "/disburse", headers=accountant, json={**payment, "amount": "41.00"})
    ).status_code == 409
    excessive = await c.post(
        base + "/disburse",
        headers=accountant,
        json={**payment, "amount": "61.00", "idempotency_key": "excess-payment"},
    )
    assert excessive.status_code == 422
    final_body = {**payment, "amount": "60.00", "idempotency_key": "payment-final"}
    final = await c.post(base + "/disburse", headers=accountant, json=final_body)
    assert final.status_code == 200, final.text
    assert final.json()["data"]["status"] == "completed"
    assert (
        await c.post(base + "/disburse", headers=accountant, json=final_body)
    ).status_code == 200
    detail = (await c.get(base, headers=auditor)).json()["data"]
    assert len(detail["disbursements"]) == 2
    assert len(detail["transactions"]) == 2
    assert not detail["allowed_actions"]
    statement = await c.get(
        f"/api/v1/finance/accounts/{payment['account_id']}/statement?from_date=2030-05-01&to_date=2030-05-31",
        headers=accountant,
    )
    assert statement.status_code == 200, statement.text
    assert statement.json()["data"]["closing_balance"] == "900.00"
    assert statement.json()["data"]["debits"] == "100.00"
    tx = detail["transactions"][0]
    reconciled = await c.post(
        f"/api/v1/finance/transactions/{tx['id']}/reconcile",
        headers=accountant,
        json={"reference": "BANK-1"},
    )
    assert reconciled.status_code == 200, reconciled.text
    reversal = {"reason": "Payment returned", "idempotency_key": "reverse-original"}
    reverse = await c.post(
        f"/api/v1/finance/transactions/{tx['id']}/reverse", headers=accountant, json=reversal
    )
    assert reverse.status_code == 200, reverse.text
    assert (
        await c.post(
            f"/api/v1/finance/transactions/{tx['id']}/reverse", headers=accountant, json=reversal
        )
    ).status_code == 200
    after = (await c.get(base, headers=staff)).json()["data"]
    assert after["voucher"]["status"] == "partially_disbursed"
    assert Decimal(after["voucher"]["outstanding_amount"]) == Decimal(tx["amount"])
    assert len(after["transactions"]) == 3
    factory = c._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        events = list(
            (
                await session.scalars(
                    select(Notification.notification_type).where(
                        Notification.notification_type.like("voucher_%")
                    )
                )
            ).all()
        )
        assert {
            "voucher_submitted",
            "voucher_approved",
            "voucher_partially_disbursed",
            "voucher_disbursed",
            "voucher_reversed",
        } <= set(events)
        assert events.count("voucher_disbursed") == 1
        history = list((await session.scalars(select(VoucherHistory.event_type))).all())
        assert history.count("disbursed") == 1


async def test_document_authorization_and_validation(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c = organization_client
    monkeypatch.setattr(get_settings(), "local_storage_path", str(tmp_path))
    staff, _ = await identity(c, "document-owner", "Employee")
    other, _ = await identity(c, "other-employee", "Employee")
    v = await create(c, staff)
    base = f"/api/v1/vouchers/{v['id']}"
    blocked = await c.post(
        base + "/attachments",
        headers=other,
        files={"file": ("receipt.txt", b"receipt", "text/plain")},
    )
    assert blocked.status_code == 404
    uploaded = await c.post(
        base + "/attachments",
        headers=staff,
        files={"file": ("../../receipt.txt", b"receipt", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()["data"]
    assert attachment["filename"] == "receipt.txt"
    assert "signature" not in str(attachment)
    assert "storage_key" not in attachment
    assert (await c.get(attachment["url"], headers=staff)).content == b"receipt"
    assert (await c.get(attachment["url"], headers=other)).status_code == 404
    for filename, data, mime in (
        ("bad.pdf", b"not a pdf", "application/pdf"),
        ("bad.html", b"content", "text/html"),
        ("empty.txt", b"", "text/plain"),
    ):
        invalid = await c.post(
            base + "/attachments", headers=staff, files={"file": (filename, data, mime)}
        )
        assert invalid.status_code == 422
    assert (
        await c.delete(base + f"/attachments/{attachment['id']}", headers=staff)
    ).status_code == 200
    assert (await c.get(attachment["url"], headers=staff)).status_code == 404
    assert (await c.post(base + "/submit", headers=staff)).status_code == 200
    assert (
        await c.post(
            base + "/attachments",
            headers=staff,
            files={"file": ("receipt.txt", b"receipt", "text/plain")},
        )
    ).status_code == 403


async def test_voucher_tenant_and_reporting_isolation(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    c = organization_client
    foreign_headers, _ = await _register_tenant(
        c, slug="foreign-finance", email="admin@foreign-finance.example"
    )
    v = await create(c, foreign_headers)
    base = f"/api/v1/vouchers/{v['id']}"
    for path in (base, base + "/attachments", base + "/pdf"):
        assert (await c.get(path, headers=admin_headers)).status_code == 404
    assert (
        await c.patch(base, headers=admin_headers, json={"title": "Invisible"})
    ).status_code == 404
    assert (
        await c.post(base + "/comments", headers=admin_headers, json={"body": "Invisible"})
    ).status_code == 404
    own_list = (await c.get("/api/v1/vouchers", headers=admin_headers)).json()["data"]
    assert own_list["total"] == 0
    unrelated, _ = await identity(c, "unrelated-manager", "Team Manager")
    staff, _ = await identity(c, "unrelated-staff", "Employee")
    local = await create(c, staff)
    await c.post(f"/api/v1/vouchers/{local['id']}/submit", headers=staff)
    assert (
        await c.post(f"/api/v1/vouchers/{local['id']}/approve", headers=unrelated, json={})
    ).status_code == 404


async def test_statement_prior_balance_and_exports(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    c = organization_client
    account = await c.post(
        "/api/v1/finance/accounts",
        headers=admin_headers,
        json={
            "account_name": "Reserve",
            "account_code": "RES",
            "account_type": "bank",
            "account_number": "1234567890",
            "opening_balance": "500.25",
        },
    )
    assert account.status_code == 201, account.text
    a = account.json()["data"]
    assert "1234567890" not in account.text
    factory = c._meetinghq_session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        actor = await session.scalar(select(User).where(User.email == "admin@northstar.example"))
        assert actor
        for index, (day, direction, amount) in enumerate(
            (
                (1, "credit", "100.15"),
                (2, "debit", "50.10"),
                (5, "credit", "20.20"),
                (8, "debit", "30.30"),
                (20, "debit", "5.00"),
            )
        ):
            session.add(
                FinanceTransaction(
                    organization_id=actor.organization_id,
                    account_id=uuid.UUID(a["id"]),
                    reference=f"TX-{index}",
                    idempotency_key=f"fixture-{index}",
                    transaction_type="adjustment",
                    direction=direction,
                    amount=Decimal(amount),
                    currency="NGN",
                    transaction_date=date(2030, 1, day),
                    description="Fixture transaction",
                    created_by_id=actor.id,
                )
            )
        await session.commit()
    path = f"/api/v1/finance/accounts/{a['id']}/statement"
    s = await c.get(path + "?from_date=2030-01-05&to_date=2030-01-08", headers=admin_headers)
    assert s.status_code == 200, s.text
    values = s.json()["data"]
    assert {k: values[k] for k in ("opening_balance", "credits", "debits", "closing_balance")} == {
        "opening_balance": "550.30",
        "credits": "20.20",
        "debits": "30.30",
        "closing_balance": "540.20",
    }
    assert [t["running_balance"] for t in values["transactions"]] == ["570.50", "540.20"]
    assert (
        await c.get(path + "?from_date=2030-02-01&to_date=2030-01-01", headers=admin_headers)
    ).status_code == 422
    pdf = await c.get(
        path + "/export?from_date=2030-01-05&to_date=2030-01-08&format=pdf", headers=admin_headers
    )
    assert pdf.status_code == 200, pdf.text[:100] if pdf.status_code != 200 else ""
    assert pdf.content.startswith(b"%PDF-")
    csv = await c.get(
        path + "/export?from_date=2030-01-05&to_date=2030-01-08", headers=admin_headers
    )
    assert "540.20" in csv.text and "550.30" in csv.text
    v = await create(c, admin_headers, title="=SUM(A1:A2)")
    voucher_pdf = await c.get(f"/api/v1/vouchers/{v['id']}/pdf", headers=admin_headers)
    assert voucher_pdf.status_code == 200, (
        voucher_pdf.text[:100] if voucher_pdf.status_code != 200 else ""
    )
    assert voucher_pdf.content.startswith(b"%PDF-")
    exported = await c.get("/api/v1/vouchers/export", headers=admin_headers)
    assert "'=SUM(A1:A2)" in exported.text
    assert str(v["id"]) not in exported.text


async def test_controlled_adjustments_and_atomic_transfers(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Finance admins can post explicit corrections and paired transfers once."""
    c = organization_client
    accounts = []
    for code in ("SOURCE", "DEST"):
        response = await c.post(
            "/api/v1/finance/accounts",
            headers=admin_headers,
            json={
                "account_name": f"{code} account",
                "account_code": code,
                "account_type": "cash",
                "opening_balance": "100.00" if code == "SOURCE" else "10.00",
            },
        )
        assert response.status_code == 201, response.text
        accounts.append(response.json()["data"])
    adjustment = {
        "account_id": accounts[0]["id"],
        "direction": "credit",
        "amount": "5.25",
        "transaction_date": "2030-06-01",
        "description": "Verified opening correction",
        "idempotency_key": "adjustment-001",
    }
    posted = await c.post(
        "/api/v1/finance/transactions/adjustments", headers=admin_headers, json=adjustment
    )
    assert posted.status_code == 201, posted.text
    assert (
        await c.post(
            "/api/v1/finance/transactions/adjustments", headers=admin_headers, json=adjustment
        )
    ).status_code == 201
    assert (
        await c.post(
            "/api/v1/finance/transactions/adjustments",
            headers=admin_headers,
            json={**adjustment, "amount": "5.26"},
        )
    ).status_code == 409
    transfer = {
        "source_account_id": accounts[0]["id"],
        "destination_account_id": accounts[1]["id"],
        "amount": "20.00",
        "transaction_date": "2030-06-02",
        "description": "Working capital transfer",
        "idempotency_key": "transfer-001",
    }
    moved = await c.post("/api/v1/finance/transfers", headers=admin_headers, json=transfer)
    assert moved.status_code == 201, moved.text
    entries = moved.json()["data"]
    assert len(entries) == 2
    assert {entry["direction"] for entry in entries} == {"credit", "debit"}
    assert len({entry["transfer_group_id"] for entry in entries}) == 1
    replay = await c.post("/api/v1/finance/transfers", headers=admin_headers, json=transfer)
    assert replay.status_code == 201
    assert (
        await c.post(
            "/api/v1/finance/transfers",
            headers=admin_headers,
            json={**transfer, "destination_account_id": accounts[0]["id"]},
        )
    ).status_code == 422
    source = await c.get(
        f"/api/v1/finance/accounts/{accounts[0]['id']}/statement?from_date=2030-06-01&to_date=2030-06-03",
        headers=admin_headers,
    )
    destination = await c.get(
        f"/api/v1/finance/accounts/{accounts[1]['id']}/statement?from_date=2030-06-01&to_date=2030-06-03",
        headers=admin_headers,
    )
    assert source.json()["data"]["closing_balance"] == "85.25"
    assert destination.json()["data"]["closing_balance"] == "30.00"


async def test_return_edit_resubmit_and_review_reasons(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    c = organization_client
    staff, _ = await identity(c, "return-staff", "Employee")
    v = await create(c, staff)
    base = f"/api/v1/vouchers/{v['id']}"
    await c.post(base + "/submit", headers=staff)
    assert (
        await c.post(base + "/return", headers=admin_headers, json={"comment": "   "})
    ).status_code == 422
    assert (
        await c.post(base + "/return", headers=admin_headers, json={"comment": "Attach receipt"})
    ).status_code == 200
    edited = await c.patch(
        base,
        headers=staff,
        json={"line_items": [{"description": "Corrected materials", "unit_price": "25.00"}]},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["requested_amount"] == "25.00"
    assert (await c.post(base + "/submit", headers=staff)).status_code == 200
    assert (
        await c.post(base + "/reject", headers=admin_headers, json={"comment": "Outside policy"})
    ).status_code == 200
    assert (await c.patch(base, headers=staff, json={"title": "Again"})).status_code == 403
    assert (await c.get("/api/v1/vouchers?page_size=11", headers=staff)).status_code == 422
