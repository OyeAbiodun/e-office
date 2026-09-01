"""Productize enterprise Teams and channels.

Revision ID: 0014_team_product
Revises: 0013_workspace_product
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014_team_product"
down_revision: str | None = "0013_workspace_product"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch:
        batch.add_column(sa.Column("avatar_url", sa.String(2048)))
        batch.add_column(sa.Column("banner_url", sa.String(2048)))
        batch.add_column(
            sa.Column(
                "classification",
                sa.String(40),
                nullable=False,
                server_default="internal",
            )
        )
        batch.add_column(
            sa.Column(
                "owner_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "users.id",
                    name="fk_teams_owner_id_users",
                    ondelete="SET NULL",
                ),
            )
        )
        batch.add_column(sa.Column("settings", json_type, nullable=False, server_default="{}"))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"])
    op.create_index("ix_teams_archived_at", "teams", ["archived_at"])

    with op.batch_alter_table("conversations") as batch:
        batch.add_column(
            sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column(
                "moderation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("settings", json_type, nullable=False, server_default="{}"))

    op.create_table(
        "team_integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "provider"),
    )
    op.create_index(
        "ix_team_integrations_organization_id", "team_integrations", ["organization_id"]
    )
    op.create_index("ix_team_integrations_team_id", "team_integrations", ["team_id"])

    op.create_table(
        "team_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(24), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("organization_id", "team_id", "document_type"):
        op.create_index(f"ix_team_documents_{column}", "team_documents", [column])

    op.create_table(
        "channel_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("conversation_id", "user_id"),
    )
    for column in ("organization_id", "conversation_id", "user_id"):
        op.create_index(f"ix_channel_preferences_{column}", "channel_preferences", [column])

    op.execute(
        """
        UPDATE teams
        SET owner_id = (
            SELECT team_members.user_id
            FROM team_members
            WHERE team_members.team_id = teams.id
              AND team_members.role = 'OWNER'
            LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_table("channel_preferences")
    op.drop_table("team_documents")
    op.drop_table("team_integrations")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("settings")
        batch.drop_column("moderation_enabled")
        batch.drop_column("read_only")
    with op.batch_alter_table("teams") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("settings")
        batch.drop_column("owner_id")
        batch.drop_column("classification")
        batch.drop_column("banner_url")
        batch.drop_column("avatar_url")
