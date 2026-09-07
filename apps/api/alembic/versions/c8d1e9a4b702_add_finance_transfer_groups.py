"""add finance transfer groups

Revision ID: c8d1e9a4b702
Revises: b73c8f51a902
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8d1e9a4b702"
down_revision: str | Sequence[str] | None = "b73c8f51a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow paired entries to be identified without changing ledger values."""
    op.add_column(
        "finance_transactions",
        sa.Column("transfer_group_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_finance_transactions_org_transfer_group",
        "finance_transactions",
        ["organization_id", "transfer_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_finance_transactions_org_transfer_group", table_name="finance_transactions")
    op.drop_column("finance_transactions", "transfer_group_id")
