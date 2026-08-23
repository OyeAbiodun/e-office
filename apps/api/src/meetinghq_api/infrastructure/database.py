"""Asynchronous SQLAlchemy infrastructure."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from meetinghq_api.core.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for module-owned persistence models."""


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
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
