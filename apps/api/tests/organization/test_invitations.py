"""Invitation flow integration tests."""

from httpx import AsyncClient
from pytest import MonkeyPatch

from meetinghq_api.modules.auth.infrastructure.email import IdentityEmailSender


async def test_invitation_acceptance(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    delivered: list[str] = []

    async def capture(
        _: IdentityEmailSender,
        email: str,
        token: str,
        organization_id: object | None = None,
    ) -> None:
        delivered.append(token)

    monkeypatch.setattr(IdentityEmailSender, "send_invitation", capture)
    invited = await organization_client.post(
        "/api/v1/invitations",
        headers=admin_headers,
        json={"email": "member@northstar.example", "role_name": "Employee"},
    )
    assert invited.status_code == 201
    assert len(delivered) == 1
    accepted = await organization_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": delivered[0],
            "username": "northstar.member",
            "first_name": "Morgan",
            "last_name": "Member",
            "password": "Secure!Password123",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["email"] == "member@northstar.example"
