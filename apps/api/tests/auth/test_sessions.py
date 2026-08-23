"""Session management integration tests."""

from httpx import AsyncClient


async def test_session_list_and_revocation(
    auth_client: AsyncClient, registration_payload: dict[str, str]
) -> None:
    """Users can enumerate and revoke only their own active sessions."""
    registered = await auth_client.post("/api/v1/auth/register", json=registration_payload)
    token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    sessions = await auth_client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    assert len(sessions.json()["data"]) == 1

    revoked = await auth_client.delete(
        f"/api/v1/auth/sessions/{sessions.json()['data'][0]['id']}", headers=headers
    )
    assert revoked.status_code == 200
    empty = await auth_client.get("/api/v1/auth/sessions", headers=headers)
    assert empty.json()["data"] == []
