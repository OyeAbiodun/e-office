"""Add explicit installation ownership and workspace access.

Revision ID: 0005_bootstrap
Revises: 0004_calendar
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_bootstrap"
down_revision: str | None = "0004_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("owner_id", sa.Uuid()))
    op.create_index("ix_organizations_owner_id", "organizations", ["owner_id"])
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(40), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_memberships_user_id",
        "workspace_memberships",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("workspace_memberships")
    op.drop_index("ix_organizations_owner_id", table_name="organizations")
    op.drop_column("organizations", "owner_id")
