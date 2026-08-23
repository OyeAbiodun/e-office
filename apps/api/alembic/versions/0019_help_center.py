"""Add tenant-managed help articles.

Revision ID: 0019_help_center
Revises: 0018_dynamic_menu_roles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_help_center"
down_revision: str | None = "0018_dynamic_menu_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "help_articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "slug", "version"),
    )
    op.create_index("ix_help_articles_organization_id", "help_articles", ["organization_id"])
    op.create_index("ix_help_articles_slug", "help_articles", ["slug"])
    op.create_index("ix_help_articles_title", "help_articles", ["title"])
    op.create_index("ix_help_articles_category", "help_articles", ["category"])
    op.execute("UPDATE menu_definitions SET enabled = TRUE WHERE key = 'help'")


def downgrade() -> None:
    op.drop_table("help_articles")
