"""Enterprise policy configuration remains isolated per organization."""

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.database import Base
from meetinghq_api.modules.configuration.service import ConfigurationRegistry
from meetinghq_api.modules.organizations.models import Organization


async def test_configuration_keys_can_never_cross_tenant_boundaries() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    async with factory() as session:
        session.add_all(
            [
                Organization(id=first_id, name="First", slug="first"),
                Organization(id=second_id, name="Second", slug="second"),
            ]
        )
        await session.flush()
        first = ConfigurationRegistry(session, get_settings(), first_id)
        second = ConfigurationRegistry(session, get_settings(), second_id)
        await first.set(
            "meeting_policy",
            {"recording": "disabled"},
            "meetings",
        )
        await second.set(
            "meeting_policy",
            {"recording": "required"},
            "meetings",
        )
        await session.flush()

        assert await first.get("meeting_policy") == {"recording": "disabled"}
        assert await second.get("meeting_policy") == {"recording": "required"}
    await engine.dispose()
