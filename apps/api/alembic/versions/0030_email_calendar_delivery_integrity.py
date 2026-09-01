"""Add the durable iCalendar update sequence.

Revision ID: 0030_calendar_delivery_sequence
Revises: 0029_tenant_query_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_calendar_delivery_sequence"
down_revision: str | None = "0029_tenant_query_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("meetings", "sequence")
