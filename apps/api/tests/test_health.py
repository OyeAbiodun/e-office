"""System endpoint tests."""

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    """Liveness succeeds without external infrastructure."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}


async def test_openapi_is_available(client: AsyncClient) -> None:
    """OpenAPI documents the versioned health endpoint."""
    response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
