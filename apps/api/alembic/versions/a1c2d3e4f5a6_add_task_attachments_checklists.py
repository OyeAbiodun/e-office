"""add task attachments and checklists

Revision ID: a1c2d3e4f5a6
Revises: 897218f41206
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "897218f41206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("url", sa.String(length=1200), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_task_attachments_organization_id", "task_attachments", ["organization_id"])
    op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])
    op.create_index("ix_task_attachments_uploaded_by_id", "task_attachments", ["uploaded_by_id"])
    op.create_index(
        "ix_task_attachments_task_created", "task_attachments", ["task_id", "created_at"]
    )
    op.create_table(
        "task_checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_checklist_items_organization_id", "task_checklist_items", ["organization_id"]
    )
    op.create_index("ix_task_checklist_items_task_id", "task_checklist_items", ["task_id"])
    op.create_index(
        "ix_task_checklist_items_completed_by_id", "task_checklist_items", ["completed_by_id"]
    )
    op.create_index(
        "ix_task_checklist_items_task_position", "task_checklist_items", ["task_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_task_checklist_items_task_position", table_name="task_checklist_items")
    op.drop_index("ix_task_checklist_items_completed_by_id", table_name="task_checklist_items")
    op.drop_index("ix_task_checklist_items_task_id", table_name="task_checklist_items")
    op.drop_index("ix_task_checklist_items_organization_id", table_name="task_checklist_items")
    op.drop_table("task_checklist_items")
    op.drop_index("ix_task_attachments_task_created", table_name="task_attachments")
    op.drop_index("ix_task_attachments_uploaded_by_id", table_name="task_attachments")
    op.drop_index("ix_task_attachments_task_id", table_name="task_attachments")
    op.drop_index("ix_task_attachments_organization_id", table_name="task_attachments")
    op.drop_table("task_attachments")
