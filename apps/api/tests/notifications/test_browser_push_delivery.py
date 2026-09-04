"""Durable Web Push outbox coverage."""

import secrets
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from meetinghq_api.core.config import Settings
from meetinghq_api.infrastructure.database import Base
from meetinghq_api.modules.notifications.models import (
    BrowserPushDelivery,
    NotificationPreference,
    PushSubscription,
)
from meetinghq_api.modules.notifications.service import NotificationService
from meetinghq_api.modules.organizations.models import Organization
from meetinghq_api.modules.users.models import User


@pytest.fixture
async def notification_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_browser_push_is_queued_and_delivered_by_the_worker(
    notification_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    organization = Organization(name="Push Test", slug="push-test")
    notification_session.add(organization)
    await notification_session.flush()
    user = User(
        organization_id=organization.id,
        email="push@example.test",
        username="push-user",
        first_name="Push",
        last_name="User",
        display_name="Push User",
        password_hash=secrets.token_urlsafe(32),
    )
    notification_session.add(user)
    await notification_session.flush()
    notification_session.add_all(
        [
            NotificationPreference(
                organization_id=organization.id,
                user_id=user.id,
                browser_enabled=True,
                timezone="UTC",
            ),
            PushSubscription(
                organization_id=organization.id,
                user_id=user.id,
                endpoint="https://push.example.test/subscription",
                p256dh="public-key",
                auth="auth-key",
                enabled=True,
            ),
        ]
    )
    await notification_session.flush()
    service = NotificationService(
        notification_session,
        Settings(
            environment="test",
            web_push_vapid_public_key="public-vapid-key",
            web_push_vapid_private_key="private-vapid-key",
            web_push_vapid_subject="mailto:security@example.test",
        ),
    )
    notification = await service.create_notification(
        organization_id=organization.id,
        user_id=user.id,
        notification_type="meeting_reminder",
        title="Meeting soon",
        body="A meeting starts soon.",
        category="meetings",
    )
    assert await notification_session.scalar(select(func.count(BrowserPushDelivery.id))) == 1

    def delivered(_: NotificationService, __: PushSubscription, ___: object) -> None:
        return None

    monkeypatch.setattr(NotificationService, "_send_web_push", delivered)
    assert await service.process_due_browser_pushes() == 1
    queued = await notification_session.scalar(
        select(BrowserPushDelivery).where(BrowserPushDelivery.notification_id == notification.id)
    )
    assert queued is not None
    assert queued.status == "sent"
    assert queued.delivered_at is not None
