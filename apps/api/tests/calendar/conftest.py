"""Calendar API integration fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.infrastructure.database import Base, get_database_session
from meetinghq_api.main import app


@pytest.fixture
async def organization_client() -> AsyncIterator[AsyncClient]:
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def admin_headers(organization_client: AsyncClient) -> dict[str, str]:
    response = await organization_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Calendar Test",
            "organization_slug": "calendar-test",
            "workspace_name": "Calendar Workspace",
            "email": "admin@calendar.example",
            "username": "calendar.admin",
            "first_name": "Calendar",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
