"""Permanent installation bootstrap acceptance tests."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from meetinghq_api.bootstrap import BootstrapInitializationService
from meetinghq_api.core.config import Settings
from meetinghq_api.infrastructure.database import Base
from meetinghq_api.modules.auth.domain.permissions import PERMISSION_CATALOG
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import User
from meetinghq_api.modules.workspaces.models import Workspace, WorkspaceMembership


async def test_bootstrap_creates_owned_installation_once() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(
        _env_file=None,
        initial_super_admin_email="bootstrap.admin@example.com",
        initial_super_admin_password="Bootstrap-Test-Only-1!",  # noqa: S106
        initial_super_admin_first_name="Platform",
        initial_super_admin_last_name="",
        initial_organization_name="MeetingHQ",
        initial_workspace_name="Main Workspace",
    )
    async with factory() as session:
        assert await BootstrapInitializationService(session, settings).initialize()
        await session.commit()
        organization = await session.scalar(select(Organization))
        workspace = await session.scalar(select(Workspace))
        user = await session.scalar(select(User))
        membership = await session.scalar(select(WorkspaceMembership))
        assert organization is not None and workspace is not None and user is not None
        assert organization.owner_id == user.id
        assert membership is not None
        assert membership.workspace_id == workspace.id
        assert membership.user_id == user.id
        assert membership.role == "owner"
        assert [role.name for role in user.roles] == ["Super Admin"]
        assert len(user.roles[0].permissions) == len(PERMISSION_CATALOG)

    async with factory() as session:
        assert not await BootstrapInitializationService(session, settings).initialize()
        await session.commit()
        assert await session.scalar(select(func.count(Organization.id))) == 1
        assert await session.scalar(select(func.count(Workspace.id))) == 1
        assert await session.scalar(select(func.count(User.id))) == 1
        assert await session.scalar(select(func.count(WorkspaceMembership.id))) == 1
    await engine.dispose()
