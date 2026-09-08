"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Enum, String, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from meetinghq_api.core.config import get_settings
from meetinghq_api.infrastructure.database import Base
from meetinghq_api.modules.activity import models as activity_models  # noqa: F401
from meetinghq_api.modules.audit import models as audit_models  # noqa: F401
from meetinghq_api.modules.auth.infrastructure import models as auth_models  # noqa: F401
from meetinghq_api.modules.calendar import models as calendar_models  # noqa: F401
from meetinghq_api.modules.chat import models as chat_models  # noqa: F401
from meetinghq_api.modules.configuration import models as configuration_models  # noqa: F401
from meetinghq_api.modules.events import models as event_models  # noqa: F401
from meetinghq_api.modules.finance import models as finance_models  # noqa: F401
from meetinghq_api.modules.help_center import models as help_models  # noqa: F401
from meetinghq_api.modules.invitations import models as invitation_models  # noqa: F401
from meetinghq_api.modules.leave import models as leave_models  # noqa: F401
from meetinghq_api.modules.mail import models as mail_models  # noqa: F401
from meetinghq_api.modules.meetings import models as meeting_models  # noqa: F401
from meetinghq_api.modules.notifications import models as notification_models  # noqa: F401
from meetinghq_api.modules.organizations import models as organization_models  # noqa: F401
from meetinghq_api.modules.system_health import models as system_health_models  # noqa: F401
from meetinghq_api.modules.tasks import models as task_models  # noqa: F401
from meetinghq_api.modules.teams import models as team_models  # noqa: F401
from meetinghq_api.modules.users import models as user_models  # noqa: F401
from meetinghq_api.modules.workspaces import models as workspace_models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def compare_type(
    _context: object,
    _inspected_column: object,
    _metadata_column: object,
    inspected_type: object,
    metadata_type: object,
) -> bool | None:
    """Treat reflected VARCHAR and non-native SQLAlchemy enums as equivalent."""
    if isinstance(metadata_type, Enum) and not metadata_type.native_enum:
        if isinstance(inspected_type, String):
            return False
    return None


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Run migrations with an existing connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations using SQLAlchemy's async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
