"""Make the configuration registry explicitly tenant scoped.

Revision ID: 0011_tenant_config
Revises: 0010_teams_channels
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011_tenant_config"
down_revision: str | None = "0010_teams_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # The registry has not yet been exposed for writes. Recreate it now so its
    # identity and uniqueness rules cannot become global tenant leak paths.
    op.drop_table("configuration_entries")
    op.create_table(
        "configuration_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("value", json_type, nullable=False, server_default="{}"),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scope", "key"),
    )
    for column in ("scope", "organization_id", "key", "category"):
        op.create_index(
            f"ix_configuration_entries_{column}",
            "configuration_entries",
            [column],
        )


def downgrade() -> None:
    op.drop_table("configuration_entries")
    op.create_table(
        "configuration_entries",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("value", json_type, nullable=False, server_default="{}"),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_configuration_entries_category", "configuration_entries", ["category"])
