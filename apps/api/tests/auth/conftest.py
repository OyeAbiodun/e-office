"""Isolated identity database and client fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.infrastructure.database import Base, get_database_session
from meetinghq_api.main import app
from meetinghq_api.modules.auth.infrastructure import models as auth_models  # noqa: F401
from meetinghq_api.modules.organizations import models as organization_models  # noqa: F401
from meetinghq_api.modules.users import models as user_models  # noqa: F401
from meetinghq_api.modules.workspaces import models as workspace_models  # noqa: F401


@pytest.fixture
async def auth_client() -> AsyncIterator[AsyncClient]:
    """Provide an API client backed by an isolated SQLite identity schema."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_database() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_database_session] = override_database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        yield client
    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.fixture
def registration_payload() -> dict[str, str]:
    """Return a valid initial tenant registration."""
    return {
        "organization_name": "Acme Collaboration",
        "organization_slug": "acme",
        "workspace_name": "Acme HQ",
        "email": "admin@acme.example",
        "username": "acme.admin",
        "first_name": "Avery",
        "last_name": "Admin",
        "password": "Secure!Password123",
    }
