"""Complete self-service profile fields.

Revision ID: 0025_profile_center_completion
Revises: 0024_capability_governance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_profile_center_completion"
down_revision: str | None = "0024_capability_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("location", sa.String(length=160)))


def downgrade() -> None:
    op.drop_column("users", "location")
