"""Add searchable keywords to Help Centre articles.

Revision ID: a4f5d6e7c801
Revises: 9b13e6f8a024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4f5d6e7c801"
down_revision: str | Sequence[str] | None = "9b13e6f8a024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "help_articles",
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("help_articles", "keywords", server_default=None)


def downgrade() -> None:
    op.drop_column("help_articles", "keywords")
