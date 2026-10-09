"""Asynchronous SQLAlchemy infrastructure."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

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


async def _shielded_cleanup(operation: Callable[[], Awaitable[object]]) -> None:
    """Finish database cleanup even when the owning request is cancelled."""
    task: asyncio.Future[object] = asyncio.ensure_future(operation())
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await task


@asynccontextmanager
async def transaction_scope(
    factory: async_sessionmaker[AsyncSession] = session_factory,
) -> AsyncIterator[AsyncSession]:
    """Commit successful work and reliably clean up every other exit path."""
    session = factory()
    try:
        try:
            yield session
            await session.commit()
        except BaseException:
            await _shielded_cleanup(session.rollback)
            raise
    finally:
        await _shielded_cleanup(session.close)


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-scoped asynchronous database session."""
    async with transaction_scope() as session:
        request.state.database_session = session
        yield session
