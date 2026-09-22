"""Add server-enforced help article permission metadata.

Revision ID: b6e1c2d3f4a5
Revises: a4f5d6e7c801
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6e1c2d3f4a5"
down_revision: str | None = "a4f5d6e7c801"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "help_articles",
        sa.Column("required_permission", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "ix_help_articles_required_permission",
        "help_articles",
        ["required_permission"],
    )
    op.execute(
        sa.text(
            "UPDATE help_articles SET required_permission = 'admin.manage' "
            "WHERE category IN ('Administrator Handbook', 'Deployment Guides', 'API Guides') "
            "OR slug = 'system-admin-learning-path'"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_help_articles_required_permission", table_name="help_articles")
    op.drop_column("help_articles", "required_permission")
