"""Access tokens cannot be replayed with a different tenant context."""

import uuid

from httpx import AsyncClient

from meetinghq_api.core.config import get_settings
from meetinghq_api.modules.auth.domain.permissions import ROLE_PERMISSIONS
from meetinghq_api.modules.auth.infrastructure.tokens import AccessTokenService


async def test_access_token_organization_must_match_persisted_identity(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    assert registered.status_code == 201
    identity = registered.json()["data"]["user"]
    mismatched = AccessTokenService(get_settings()).create(
        uuid.UUID(identity["id"]),
        uuid.uuid4(),
        ROLE_PERMISSIONS["Admin"],
    )

    response = await auth_client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {mismatched}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"
