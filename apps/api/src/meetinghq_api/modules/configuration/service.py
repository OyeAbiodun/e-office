"""Single registry for environment defaults and future persisted overrides."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.modules.configuration.models import ConfigurationEntry


class ConfigurationRegistry:
    """Read configuration through one extensible boundary."""

    def __init__(
        self, session: AsyncSession, settings: Settings, organization_id: uuid.UUID
    ) -> None:
        self._session = session
        self._settings = settings
        self._organization_id = organization_id
        self._scope = f"organization:{organization_id}"

    async def get(self, key: str, default: Any = None) -> Any:
        entry = await self._session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.scope == self._scope,
                ConfigurationEntry.organization_id == self._organization_id,
                ConfigurationEntry.key == key,
            )
        )
        if entry is not None:
            return entry.value
        return getattr(self._settings, key, default)

    async def set(
        self,
        key: str,
        value: dict[str, object],
        category: str,
        actor_id: uuid.UUID | None = None,
    ) -> None:
        entry = await self._session.scalar(
            select(ConfigurationEntry).where(
                ConfigurationEntry.scope == self._scope,
                ConfigurationEntry.organization_id == self._organization_id,
                ConfigurationEntry.key == key,
            )
        )
        if entry is None:
            self._session.add(
                ConfigurationEntry(
                    scope=self._scope,
                    organization_id=self._organization_id,
                    key=key,
                    value=value,
                    category=category,
                    updated_by=actor_id,
                )
            )
        else:
            entry.value = value
            entry.category = category
            entry.updated_by = actor_id
