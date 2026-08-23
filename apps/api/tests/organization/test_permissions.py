"""Organization endpoint authorization tests."""

from httpx import AsyncClient


async def test_management_endpoints_require_authentication(
    organization_client: AsyncClient,
) -> None:
    for path in ("/api/v1/organizations/current", "/api/v1/workspaces", "/api/v1/teams"):
        response = await organization_client.get(path)
        assert response.status_code == 401
