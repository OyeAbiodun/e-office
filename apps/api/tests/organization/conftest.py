"""Organization management test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.infrastructure.database import Base, get_database_session
from meetinghq_api.main import app


@pytest.fixture
async def organization_client() -> AsyncIterator[AsyncClient]:
    """Provide an isolated fully migrated logical schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def database_override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_database_session] = database_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        # Focused service tests can exercise scheduled work against this same
        # isolated schema without reaching the shared local runtime.
        client._meetinghq_session_factory = factory  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def admin_headers(organization_client: AsyncClient) -> dict[str, str]:
    """Register a tenant and return administrator authorization."""
    response = await organization_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Northstar",
            "organization_slug": "northstar",
            "workspace_name": "Northstar HQ",
            "email": "admin@northstar.example",
            "username": "northstar.admin",
            "first_name": "Nora",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
