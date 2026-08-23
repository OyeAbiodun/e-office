"""Storage provider tests."""

import io
from pathlib import Path

from httpx import AsyncClient

from meetinghq_api.core.config import get_settings
from meetinghq_api.main import app
from meetinghq_api.modules.storage.local import LocalStorageProvider, sign_storage_key


async def test_local_storage_uses_opaque_safe_keys(tmp_path: Path) -> None:
    provider = LocalStorageProvider(str(tmp_path), "/api/v1/storage", "test-secret")
    stored = await provider.put(
        "organizations/tenant/avatars",
        io.BytesIO(b"image"),
        "image/png",
        5,
    )
    assert ".." not in stored.key
    assert stored.url.endswith(f"?signature={sign_storage_key(stored.key, 'test-secret')}")
    await provider.delete(stored.key)


async def test_storage_delivery_requires_the_owning_tenant(
    tmp_path: Path,
    organization_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    other = await organization_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Contoso",
            "organization_slug": "contoso-files",
            "workspace_name": "Contoso HQ",
            "email": "files@contoso.example",
            "username": "contoso.files",
            "first_name": "Contoso",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert other.status_code == 201
    other_headers = {"Authorization": f"Bearer {other.json()['data']['access_token']}"}
    profile = await organization_client.get("/api/v1/profile", headers=admin_headers)
    organization_id = profile.json()["data"]["organization_id"]
    settings = get_settings().model_copy(update={"local_storage_path": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: settings
    provider = LocalStorageProvider(str(tmp_path), "/api/v1/storage", settings.jwt_secret)
    stored = await provider.put(
        f"organizations/{organization_id}/documents",
        io.BytesIO(b"tenant secret"),
        "application/octet-stream",
        13,
    )

    anonymous = await organization_client.get(stored.url)
    cross_tenant = await organization_client.get(stored.url, headers=other_headers)
    owner = await organization_client.get(stored.url, headers=admin_headers)

    assert anonymous.status_code == 401
    assert cross_tenant.status_code == 404
    assert owner.status_code == 200
    assert owner.content == b"tenant secret"
