"""Chat API fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.infrastructure.database import Base, get_database_session
from meetinghq_api.main import app


@pytest.fixture
async def chat_client() -> AsyncIterator[AsyncClient]:
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
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def chat_identity(chat_client: AsyncClient) -> tuple[dict[str, str], str]:
    response = await chat_client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Chat Test",
            "organization_slug": "chat-test",
            "workspace_name": "Chat Workspace",
            "email": "admin@chat.example",
            "username": "chat.admin",
            "first_name": "Chat",
            "last_name": "Admin",
            "password": "Secure!Password123",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
    workspaces = await chat_client.get("/api/v1/workspaces", headers=headers)
    return headers, workspaces.json()["data"][0]["id"]
