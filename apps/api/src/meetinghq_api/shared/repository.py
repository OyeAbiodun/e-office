"""Persistence ports and reusable SQLAlchemy repository base."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import Base


class SqlAlchemyRepository[ModelT: Base]:
    """Small persistence adapter shared by module-owned repositories."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def scalar(self, statement: Select[Any]) -> Any:
        return await self.session.scalar(statement)

    async def all(self, statement: Select[Any]) -> Sequence[Any]:
        return (await self.session.scalars(statement)).all()

    async def count(self, statement: Select[Any]) -> int:
        result = await self.session.scalar(select(func.count()).select_from(statement.subquery()))
        return int(result or 0)
