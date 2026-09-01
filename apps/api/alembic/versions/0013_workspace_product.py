"""Productize enterprise workspace administration.

Revision ID: 0013_workspace_product
Revises: 0012_org_product
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0013_workspace_product"
down_revision: str | None = "0012_org_product"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("workspaces")}
    with op.batch_alter_table("workspaces") as batch:
        if "classification" not in columns:
            batch.add_column(
                sa.Column(
                    "classification",
                    sa.String(40),
                    nullable=False,
                    server_default="internal",
                )
            )
        if "visibility" not in columns:
            batch.add_column(
                sa.Column(
                    "visibility",
                    sa.String(40),
                    nullable=False,
                    server_default="members",
                )
            )
        if "data_region" not in columns:
            batch.add_column(sa.Column("data_region", sa.String(80)))
        if "owner_id" not in columns:
            batch.add_column(
                sa.Column(
                    "owner_id",
                    sa.Uuid(),
                    sa.ForeignKey(
                        "users.id",
                        name="fk_workspaces_owner_id_users",
                        ondelete="SET NULL",
                    ),
                )
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("workspaces")}
    if "ix_workspaces_owner_id" not in indexes:
        op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    op.create_table(
        "workspace_integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "provider"),
    )
    op.create_index(
        "ix_workspace_integrations_organization_id",
        "workspace_integrations",
        ["organization_id"],
    )
    op.create_index(
        "ix_workspace_integrations_workspace_id",
        "workspace_integrations",
        ["workspace_id"],
    )

    op.create_table(
        "workspace_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("configuration", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name"),
    )
    op.create_index(
        "ix_workspace_templates_organization_id",
        "workspace_templates",
        ["organization_id"],
    )

    # Existing primary workspaces gain an explicit owner from their owner membership.
    op.execute(
        """
        UPDATE workspaces
        SET owner_id = (
            SELECT workspace_memberships.user_id
            FROM workspace_memberships
            WHERE workspace_memberships.workspace_id = workspaces.id
              AND workspace_memberships.role = 'owner'
            LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_table("workspace_templates")
    op.drop_table("workspace_integrations")
    op.drop_index("ix_workspaces_owner_id", table_name="workspaces")
    op.drop_column("workspaces", "owner_id")
    op.drop_column("workspaces", "data_region")
    op.drop_column("workspaces", "visibility")
    op.drop_column("workspaces", "classification")
