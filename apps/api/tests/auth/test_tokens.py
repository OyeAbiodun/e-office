"""Token rotation and access token tests."""

import uuid

import jwt
from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.auth.infrastructure.email import IdentityEmailSender
from meetinghq_api.modules.auth.infrastructure.tokens import (
    AccessTokenService,
    create_opaque_token,
    hash_token,
)


def test_access_token_validates_type_and_context() -> None:
    """Access tokens preserve tenant and permission context."""
    settings = Settings(jwt_secret="test-secret-value-with-at-least-32-characters")  # noqa: S106
    service = AccessTokenService(settings)
    user_id, organization_id = uuid.uuid4(), uuid.uuid4()
    encoded = service.create(user_id, organization_id, {"users.read"})
    claims = service.decode(encoded)
    assert claims["sub"] == str(user_id)
    assert claims["org"] == str(organization_id)
    assert claims["permissions"] == ["users.read"]


def test_opaque_tokens_are_random_and_hashable() -> None:
    """Refresh token storage uses stable hashes of unique credentials."""
    first, second = create_opaque_token(), create_opaque_token()
    assert first != second
    assert hash_token(first) == hash_token(first)
    assert first not in hash_token(first)


async def test_refresh_rotation_rejects_replay(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """A used refresh token cannot be rotated twice."""
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    original = registered.json()["data"]["refresh_token"]
    rotated = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": original})
    assert rotated.status_code == 200
    assert rotated.json()["data"]["refresh_token"] != original
    replay = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": original})
    assert replay.status_code == 401


async def test_cookie_refresh_allows_brief_retry_after_aborted_navigation(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """A browser can recover when navigation aborts a just-rotated cookie response."""
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    original_refresh = registered.cookies["meetinghq_refresh"]
    original_csrf = registered.cookies["meetinghq_csrf"]

    rotated = await auth_client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={"X-CSRF-Token": original_csrf},
    )
    assert rotated.status_code == 200

    auth_client.cookies.set(
        "meetinghq_refresh",
        original_refresh,
        path="/api/v1/auth",
    )
    auth_client.cookies.set("meetinghq_csrf", original_csrf, path="/")
    recovered = await auth_client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={"X-CSRF-Token": original_csrf},
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"]["refresh_token"] != original_refresh


async def test_password_reset_delivery_is_audited_single_use_and_replay_safe(
    auth_client: AsyncClient,
    registration_payload: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    delivered_tokens: list[str] = []

    async def capture(
        _sender: IdentityEmailSender,
        _email: str,
        token: str,
        _organization_id: uuid.UUID | None = None,
    ) -> None:
        delivered_tokens.append(token)

    monkeypatch.setattr(IdentityEmailSender, "send_password_reset", capture)
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    assert registered.status_code == 201
    access_token = registered.json()["data"]["access_token"]

    requested = await auth_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": registration_payload["email"]},
    )
    assert requested.status_code == 200
    assert len(delivered_tokens) == 1

    audit = await auth_client.get(
        "/api/v1/audit?action=auth.password_reset_requested",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert audit.status_code == 200
    assert audit.json()["data"]["total"] == 1
    metadata = audit.json()["data"]["items"][0]["metadata"]
    assert metadata == {"recipient_domain": "acme.example"}
    assert delivered_tokens[0] not in audit.text

    new_password = "Changed!Password456"
    reset = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": delivered_tokens[0], "new_password": new_password},
    )
    assert reset.status_code == 200
    replay = await auth_client.post(
        "/api/v1/auth/reset-password",
        json={"token": delivered_tokens[0], "new_password": "Another!Password789"},
    )
    assert replay.status_code == 401
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": registration_payload["email"], "password": new_password},
    )
    assert login.status_code == 200


def test_rejects_non_access_jwt() -> None:
    """Token type confusion is explicitly rejected."""
    settings = Settings(jwt_secret="test-secret-value-with-at-least-32-characters")  # noqa: S106
    token = jwt.encode(
        {"type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    try:
        AccessTokenService(settings).decode(token)
    except jwt.InvalidTokenError:
        return
    raise AssertionError("Non-access JWT was accepted")
