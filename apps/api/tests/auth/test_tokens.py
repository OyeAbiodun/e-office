"""Token rotation and access token tests."""

import uuid

import jwt
from httpx import AsyncClient

from meetinghq_api.core.config import Settings
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
