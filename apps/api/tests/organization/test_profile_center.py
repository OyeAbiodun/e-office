"""Self-service Profile Center integration and isolation coverage."""

from pathlib import Path

from httpx import AsyncClient

from meetinghq_api.core.config import get_settings
from meetinghq_api.main import app


async def test_profile_updates_only_the_authenticated_identity(
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    updated = await organization_client.patch(
        "/api/v1/profile",
        headers=admin_headers,
        json={
            "first_name": "Nora",
            "last_name": "Northstar",
            "display_name": "Nora Northstar",
            "phone": "+1 555 0100",
            "job_title": "Operations Director",
            "department": "Operations",
            "location": "Chicago",
            "timezone": "America/Chicago",
            "language": "en",
        },
    )

    assert updated.status_code == 200
    profile = updated.json()["data"]
    assert profile["display_name"] == "Nora Northstar"
    assert profile["location"] == "Chicago"
    assert profile["department"] == "Operations"


async def test_avatar_upload_validates_content_and_supports_removal(
    tmp_path: Path,
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    settings = get_settings().model_copy(update={"local_storage_path": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: settings
    png = b"\x89PNG\r\n\x1a\n" + b"profile-image"

    invalid = await organization_client.post(
        "/api/v1/profile/avatar",
        headers=admin_headers,
        files={"avatar": ("avatar.png", b"not-an-image", "image/png")},
    )
    assert invalid.status_code == 422

    uploaded = await organization_client.post(
        "/api/v1/profile/avatar",
        headers=admin_headers,
        files={"avatar": ("avatar.png", png, "image/png")},
    )
    assert uploaded.status_code == 200
    avatar_url = uploaded.json()["data"]["avatar_url"]
    assert avatar_url.startswith("/api/v1/storage/organizations/")

    delivered = await organization_client.get(avatar_url, headers=admin_headers)
    assert delivered.status_code == 200
    assert delivered.content == png

    removed = await organization_client.delete("/api/v1/profile/avatar", headers=admin_headers)
    assert removed.status_code == 200
    assert removed.json()["data"]["avatar_url"] is None

    app.dependency_overrides.pop(get_settings, None)
