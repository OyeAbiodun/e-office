"""Organization-owned employee directory and RBAC contract tests."""

from datetime import date

from httpx import AsyncClient

from tests.organization.test_tenant_isolation import _register_tenant


async def test_employee_lifecycle_history_department_and_custom_role(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Employment data remains tenant scoped and has an effective-dated audit trail."""
    workspace_response = await organization_client.get("/api/v1/workspaces", headers=admin_headers)
    workspace_id = workspace_response.json()["data"][0]["id"]

    department_response = await organization_client.post(
        "/api/v1/organizations/current/units",
        headers=admin_headers,
        json={
            "unit_type": "department",
            "name": "Product",
            "code": "PRODUCT",
            "description": "Product organization",
            "status": "active",
        },
    )
    assert department_response.status_code == 201, department_response.text
    department_id = department_response.json()["data"]["id"]

    permissions = await organization_client.get("/api/v1/permissions", headers=admin_headers)
    assert permissions.status_code == 200
    custom_role = await organization_client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={
            "name": "Product contributor",
            "description": "Can contribute to product planning.",
            "permission_ids": [permissions.json()["data"][0]["id"]],
        },
    )
    assert custom_role.status_code == 201, custom_role.text
    role_id = custom_role.json()["data"]["id"]

    employee_response = await organization_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Elliot",
            "last_name": "Employee",
            "email": "elliot.employee@northstar.example",
            "workspace_id": workspace_id,
            "department_id": department_id,
            "employee_number": "NORTH-001",
            "employment_status": "probation",
            "employment_type": "permanent",
            "employment_start_date": "2026-01-05",
            "role_ids": [role_id],
            "temporary_password": "Temporary!Password123",
            "send_welcome_email": False,
        },
    )
    assert employee_response.status_code == 201, employee_response.text
    employee = employee_response.json()["data"]
    assert employee["department_id"] == department_id
    assert employee["employee_number"] == "NORTH-001"
    assert employee["employment_status"] == "probation"

    directory = await organization_client.get(
        "/api/v1/employees",
        headers=admin_headers,
        params={"department_id": department_id, "search": "NORTH-001"},
    )
    assert directory.status_code == 200, directory.text
    assert [row["id"] for row in directory.json()["data"]["items"]] == [employee["id"]]

    updated = await organization_client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=admin_headers,
        json={
            "employment_status": "active",
            "employment_confirmation_date": "2026-04-05",
            "effective_date": "2026-04-05",
            "employment_change_reason": "Probation completed",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["employment_status"] == "active"

    history = await organization_client.get(
        f"/api/v1/employees/{employee['id']}/history", headers=admin_headers
    )
    assert history.status_code == 200, history.text
    assert {entry["change_type"] for entry in history.json()["data"]["items"]} >= {
        "hired",
        "employment_updated",
    }

    terminated = await organization_client.post(
        f"/api/v1/employees/{employee['id']}/terminate",
        headers=admin_headers,
        json={
            "effective_date": date(2026, 8, 1).isoformat(),
            "reason": "Contract ended",
            "disable_account": True,
        },
    )
    assert terminated.status_code == 200, terminated.text
    assert terminated.json()["data"]["employment_status"] == "terminated"
    assert terminated.json()["data"]["status"] == "suspended"

    rehired = await organization_client.post(
        f"/api/v1/employees/{employee['id']}/rehire",
        headers=admin_headers,
        json={"effective_date": "2026-09-01", "reason": "Rehired"},
    )
    assert rehired.status_code == 200, rehired.text
    assert rehired.json()["data"]["employment_status"] == "active"
    assert rehired.json()["data"]["status"] == "active"

    detail = await organization_client.get(
        f"/api/v1/organizations/current/departments/{department_id}", headers=admin_headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["employee_count"] == 1

    clone = await organization_client.post(
        f"/api/v1/roles/{role_id}/clone",
        headers=admin_headers,
        json={"name": "Product reviewer"},
    )
    assert clone.status_code == 201, clone.text
    assert clone.json()["data"]["member_count"] == 0


async def test_employee_records_and_departments_are_tenant_isolated(
    organization_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """A user may not view another tenant's employee or organization unit IDs."""
    other_headers, _ = await _register_tenant(
        organization_client, slug="fabrikam", email="admin@fabrikam.example"
    )
    other_department = await organization_client.post(
        "/api/v1/organizations/current/units",
        headers=other_headers,
        json={"unit_type": "department", "name": "Fabrikam Operations", "code": "OPS"},
    )
    assert other_department.status_code == 201, other_department.text
    department_id = other_department.json()["data"]["id"]

    inaccessible = await organization_client.get(
        f"/api/v1/organizations/current/departments/{department_id}", headers=admin_headers
    )
    assert inaccessible.status_code == 404
