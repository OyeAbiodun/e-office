"""Application-level dependency providers."""

from fastapi import HTTPException, status
from sqlalchemy import text

from meetinghq_api.infrastructure.database import engine
from meetinghq_api.infrastructure.redis import redis_client


async def check_database() -> None:
    """Raise a service error when PostgreSQL is unavailable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error


async def check_redis() -> None:
    """Raise a service error when Redis is unavailable."""
    try:
        await redis_client.ping()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        ) from error
