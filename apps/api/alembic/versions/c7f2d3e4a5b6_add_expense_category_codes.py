"""Add optional organization-scoped expense category codes.

Revision ID: c7f2d3e4a5b6
Revises: b6e1c2d3f4a5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f2d3e4a5b6"
down_revision: str | None = "b6e1c2d3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("expense_categories") as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_expense_categories_org_code", ["organization_id", "code"]
        )


def downgrade() -> None:
    with op.batch_alter_table("expense_categories") as batch_op:
        batch_op.drop_constraint("uq_expense_categories_org_code", type_="unique")
        batch_op.drop_column("code")
