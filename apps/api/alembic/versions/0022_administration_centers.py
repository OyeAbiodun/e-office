"""Enable completed System Health and Audit Center modules.

Revision ID: 0022_administration_centers
Revises: 0021_notification_center
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022_administration_centers"
down_revision: str | None = "0021_notification_center"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE menu_definitions SET enabled = TRUE, hidden = FALSE "
        "WHERE key IN ('health', 'audit')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE menu_definitions SET enabled = FALSE, hidden = TRUE "
        "WHERE key IN ('health', 'audit')"
    )
