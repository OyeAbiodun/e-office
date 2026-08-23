"""Add role-aware dynamic menu definitions.

Revision ID: 0018_dynamic_menu_roles
Revises: 0017_platform_management
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_dynamic_menu_roles"
down_revision: str | None = "0017_platform_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("menu_definitions") as batch:
        batch.add_column(sa.Column("required_role", sa.String(80)))
    op.execute(
        "UPDATE menu_definitions SET section = 'admin', "
        "parent_key = 'administration', required_role = 'Super Admin' "
        "WHERE key IN ('users', 'roles', 'platform', 'health', 'audit', "
        "'organization-settings')"
    )
    op.execute(
        "UPDATE menu_definitions SET enabled = FALSE "
        "WHERE key IN ('mail', 'notifications', 'health', 'audit', 'help')"
    )


def downgrade() -> None:
    with op.batch_alter_table("menu_definitions") as batch:
        batch.drop_column("required_role")
