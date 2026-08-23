"""Authentication API integration coverage."""

from httpx import AsyncClient

from meetinghq_api.modules.auth.infrastructure.totp import generate_totp


async def test_register_login_and_current_user(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """A new organization administrator can authenticate and resolve identity."""
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    assert registered.status_code == 201
    payload = registered.json()["data"]
    assert payload["user"]["roles"] == ["Admin"]
    assert "users.write" in payload["user"]["permissions"]
    assert payload["refresh_token"]
    assert registered.cookies.get("meetinghq_refresh")
    set_cookies = registered.headers.get_list("set-cookie")
    assert any(
        cookie.startswith("meetinghq_refresh=") and "Path=/api/v1/auth" in cookie
        for cookie in set_cookies
    )
    assert any(
        cookie.startswith("meetinghq_csrf=") and "Path=/" in cookie for cookie in set_cookies
    )

    current = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert current.status_code == 200
    assert current.json()["data"]["email"] == "admin@acme.example"

    logged_in = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@acme.example",
            "password": "Secure!Password123",
            "device_name": "Integration test",
        },
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["data"]["user"]["organization_id"] == payload["user"]["organization_id"]


async def test_registration_rejects_duplicate_tenant(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """Organization slugs are globally unique."""
    assert (
        await auth_client.post("/api/v1/auth/register", json=registration_payload)
    ).status_code == 201
    duplicate = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


async def test_login_does_not_reveal_identity_state(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """Invalid passwords receive a generic response."""
    await auth_client.post("/api/v1/auth/register", json=registration_payload)
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@acme.example",
            "password": "incorrect",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid credentials or account unavailable"


async def test_password_policy_and_confirmation_fail_as_validation_errors(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    weak = {**registration_payload, "password": "alllowercasepassword"}
    rejected = await auth_client.post("/api/v1/auth/register", json=weak)
    assert rejected.status_code == 422

    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    headers = {"Authorization": f"Bearer {registered.json()['data']['access_token']}"}
    mismatch = await auth_client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": registration_payload["password"],
            "new_password": "Another!SecurePassword123",
            "confirm_new_password": "Different!SecurePassword123",
        },
    )
    assert mismatch.status_code == 422


async def test_mfa_enrollment_requires_second_factor_on_login(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """Enabled TOTP MFA blocks password-only login and accepts valid factors."""
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup = await auth_client.post("/api/v1/profile/mfa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["data"]["secret"]
    assert setup.json()["data"]["qr_code_data_url"].startswith("data:image/svg+xml;base64,")

    verified = await auth_client.post(
        "/api/v1/profile/mfa/verify",
        headers=headers,
        json={"code": generate_totp(secret)},
    )
    assert verified.status_code == 200
    recovery_code = verified.json()["data"]["recovery_codes"][0]

    regenerated = await auth_client.post(
        "/api/v1/profile/mfa/recovery-codes",
        headers=headers,
        json={
            "current_password": "Secure!Password123",
            "code": generate_totp(secret),
        },
    )
    assert regenerated.status_code == 200
    assert len(regenerated.json()["data"]["recovery_codes"]) == 10
    recovery_code = regenerated.json()["data"]["recovery_codes"][0]

    password_only = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.example", "password": "Secure!Password123"},
    )
    assert password_only.status_code == 401
    assert password_only.json()["error"]["message"] == "Multi-factor authentication code required"

    with_totp = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@acme.example",
            "password": "Secure!Password123",
            "mfa_code": generate_totp(secret),
        },
    )
    assert with_totp.status_code == 200

    with_recovery = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@acme.example",
            "password": "Secure!Password123",
            "mfa_code": recovery_code,
        },
    )
    assert with_recovery.status_code == 200
