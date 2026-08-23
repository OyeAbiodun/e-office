"""Internal Mail delivery, tenancy, and mailbox workflow coverage."""

from httpx import AsyncClient


async def test_internal_mail_draft_delivery_and_tenant_isolation(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    admin_headers, workspace_id = meeting_identity
    roles = (await meeting_client.get("/api/v1/roles", headers=admin_headers)).json()["data"]
    employee_role = next(role for role in roles if role["name"] == "Employee")
    created_user = await meeting_client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "first_name": "Avery",
            "last_name": "Recipient",
            "email": "avery@meeting-test.example",
            "workspace_id": workspace_id,
            "role_ids": [employee_role["id"]],
            "temporary_password": "Recipient123!",
            "send_welcome_email": False,
        },
    )
    assert created_user.status_code == 201, created_user.text

    draft = await meeting_client.post(
        "/api/v1/mail/drafts",
        headers=admin_headers,
        json={
            "to_recipients": [{"email": "avery@meeting-test.example", "name": "Avery"}],
            "cc_recipients": [],
            "bcc_recipients": [],
            "subject": "Quarterly planning",
            "body_html": "<p>Please review the attached plan.</p>",
            "body_text": "Please review the attached plan.",
            "read_receipt_requested": True,
        },
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["data"]["id"]

    sent = await meeting_client.post(f"/api/v1/mail/drafts/{draft_id}/send", headers=admin_headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["folder"] == "sent"
    assert sent.json()["data"]["delivery_status"] == "delivered"

    recipient_login = await meeting_client.post(
        "/api/v1/auth/login",
        json={"email": "avery@meeting-test.example", "password": "Recipient123!"},
    )
    assert recipient_login.status_code == 200
    recipient_headers = {
        "Authorization": f"Bearer {recipient_login.json()['data']['access_token']}"
    }
    inbox = await meeting_client.get("/api/v1/mail/messages", headers=recipient_headers)
    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["data"]["unread"] == 1
    delivered = inbox.json()["data"]["items"][0]
    assert delivered["subject"] == "Quarterly planning"
    assert delivered["from_email"] == "admin@meetings.example"
    assert delivered["bcc_recipients"] == []

    read = await meeting_client.post(
        f"/api/v1/mail/messages/{delivered['id']}/read?value=true",
        headers=recipient_headers,
    )
    assert read.status_code == 200
    assert read.json()["data"]["is_read"] is True

    sender_copy = await meeting_client.get(
        f"/api/v1/mail/messages/{draft_id}", headers=admin_headers
    )
    assert sender_copy.json()["data"]["delivery_status"] == "read"

    other_tenant = await meeting_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Separate Tenant",
            "organization_slug": "separate-tenant",
            "workspace_name": "Operations",
            "email": "admin@separate.example",
            "username": "separate.admin",
            "first_name": "Separate",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_tenant.json()['data']['access_token']}"}
    isolated = await meeting_client.get(
        f"/api/v1/mail/messages/{delivered['id']}", headers=other_headers
    )
    assert isolated.status_code == 404


async def test_external_mail_requires_integration_center_configuration(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    status = await meeting_client.get("/api/v1/mail/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["data"] == {
        "internal_delivery": True,
        "external_delivery": False,
        "provider": None,
        "configuration_url": "/integrations",
    }
    draft = await meeting_client.post(
        "/api/v1/mail/drafts",
        headers=headers,
        json={
            "to_recipients": [{"email": "external@example.com"}],
            "subject": "External delivery",
            "body_text": "This requires a configured provider.",
        },
    )
    assert draft.status_code == 201, draft.text
    sent = await meeting_client.post(
        f"/api/v1/mail/drafts/{draft.json()['data']['id']}/send", headers=headers
    )
    assert sent.status_code == 409
    assert "Integration Center" in sent.json()["error"]["message"]


async def test_mail_draft_sanitizes_active_html(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    response = await meeting_client.post(
        "/api/v1/mail/drafts",
        headers=headers,
        json={
            "to_recipients": [{"email": "recipient@example.com"}],
            "subject": "Safe message",
            "body_html": (
                '<p onclick="alert(1)">Hello</p>'
                '<script>alert("stored-xss")</script>'
                '<a href="javascript:alert(1)">unsafe</a>'
            ),
        },
    )

    assert response.status_code == 201, response.text
    body_html = response.json()["data"]["body_html"]
    assert "<script" not in body_html
    assert "onclick" not in body_html
    assert "javascript:" not in body_html
    assert "<p>Hello</p>" in body_html
