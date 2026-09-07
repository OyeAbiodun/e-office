"""add optional tenant-scoped voucher task link

Revision ID: d9e2f0a5c103
Revises: c8d1e9a4b702
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "d9e2f0a5c103"
down_revision = "c8d1e9a4b702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vouchers", sa.Column("task_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_vouchers_task_id_tasks", "vouchers", "tasks", ["task_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_vouchers_task_id", "vouchers", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_vouchers_task_id", table_name="vouchers")
    op.drop_constraint("fk_vouchers_task_id_tasks", "vouchers", type_="foreignkey")
    op.drop_column("vouchers", "task_id")
