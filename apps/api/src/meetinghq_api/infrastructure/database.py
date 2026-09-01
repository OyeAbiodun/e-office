"""Asynchronous SQLAlchemy infrastructure."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from meetinghq_api.core.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for module-owned persistence models."""


settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
    )
engine = create_async_engine(settings.database_url, **engine_options)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped asynchronous database session."""
    async with session_factory() as session:
        request.state.database_session = session
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
