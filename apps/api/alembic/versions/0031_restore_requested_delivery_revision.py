"""Adopt the canonical delivery-integrity revision identifier.

Revision ID: 0030_email_calendar_delivery_integrity
Revises: 0030_calendar_delivery_sequence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_email_calendar_delivery_integrity"
down_revision: str | None = "0030_calendar_delivery_sequence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow descriptive Alembic revision identifiers before stamping this revision."""
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Keep the widened metadata column so the current revision can be downgraded safely."""
