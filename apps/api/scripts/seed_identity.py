"""Seed the environment-configured platform Super Admin."""

import asyncio

from sqlalchemy import select

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.database import session_factory
from meetinghq_api.modules.auth.application.service import AuthService
from meetinghq_api.modules.auth.presentation.schemas import RegisterRequest
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import Role, User


async def seed() -> None:
    """Idempotently create the platform tenant and Super Admin."""
    settings = get_settings()
    if not settings.super_admin_email or not settings.super_admin_password:
        raise RuntimeError(
            "MEETINGHQ_SUPER_ADMIN_EMAIL and MEETINGHQ_SUPER_ADMIN_PASSWORD are required"
        )
    async with session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.super_admin_email.lower())
        )
        if existing:
            return
        service = AuthService(session, settings)
        response = await service.register(
            RegisterRequest(
                organization_name="MeetingHQ Platform",
                organization_slug="meetinghq-platform",
                workspace_name="Platform Operations",
                email=settings.super_admin_email,
                username="superadmin",
                first_name=settings.super_admin_first_name,
                last_name=settings.super_admin_last_name,
                password=settings.super_admin_password,
            ),
            ip_address=None,
            user_agent="identity-seed",
        )
        organization = await session.scalar(
            select(Organization).where(Organization.id == response.user.organization_id)
        )
        super_admin_role = await session.scalar(
            select(Role).where(
                Role.organization_id == response.user.organization_id,
                Role.name == "Super Admin",
            )
        )
        user = await session.scalar(select(User).where(User.id == response.user.id))
        if organization is None or super_admin_role is None or user is None:
            raise RuntimeError("Super Admin seed failed")
        user.roles = [super_admin_role]
        user.email_verified = True
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
