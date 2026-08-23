"""Add MVP user administration identity fields.

Revision ID: 0015_mvp_identity
Revises: 0014_team_product
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_mvp_identity"
down_revision: str | None = "0014_team_product"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(40)))
        batch.add_column(sa.Column("job_title", sa.String(120)))
        batch.add_column(sa.Column("department", sa.String(120)))
        batch.add_column(
            sa.Column(
                "workspace_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "workspaces.id",
                    name="fk_users_workspace_id_workspaces",
                    ondelete="SET NULL",
                ),
            )
        )
        batch.add_column(
            sa.Column(
                "team_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "teams.id",
                    name="fk_users_team_id_teams",
                    ondelete="SET NULL",
                ),
            )
        )
        batch.add_column(
            sa.Column(
                "force_password_change",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    op.create_index("ix_users_department", "users", ["department"])
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.create_index("ix_users_team_id", "users", ["team_id"])
    op.create_index("ux_users_email_global", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_users_email_global", table_name="users")
    op.drop_index("ix_users_team_id", table_name="users")
    op.drop_index("ix_users_workspace_id", table_name="users")
    op.drop_index("ix_users_department", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("force_password_change")
        batch.drop_column("team_id")
        batch.drop_column("workspace_id")
        batch.drop_column("department")
        batch.drop_column("job_title")
        batch.drop_column("phone")
