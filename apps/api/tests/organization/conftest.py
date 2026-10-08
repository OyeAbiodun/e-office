"""Organization management test fixtures."""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.infrastructure.database import Base, get_database_session
from meetinghq_api.main import app


@pytest.fixture
async def organization_client() -> AsyncIterator[AsyncClient]:
    """Provide an isolated fully migrated logical schema."""
    database_url = os.getenv("MEETINGHQ_TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        if database_url.startswith("postgresql"):
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        await connection.run_sync(Base.metadata.create_all)

    async def database_override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    previous_audit_factory = getattr(app.state, "audit_session_factory", None)
    app.state.audit_session_factory = factory if database_url.startswith("postgresql") else None
    app.dependency_overrides[get_database_session] = database_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as client:
            # Focused service tests can exercise scheduled and audit work against
            # this same isolated schema without reaching the shared local runtime.
            client._meetinghq_session_factory = factory  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
        app.state.audit_session_factory = previous_audit_factory
    if database_url.startswith("postgresql"):
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
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
