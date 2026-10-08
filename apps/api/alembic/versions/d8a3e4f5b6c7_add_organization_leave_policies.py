"""Add organization leave policies and request workflow fields.

Revision ID: d8a3e4f5b6c7
Revises: c7f2d3e4a5b6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8a3e4f5b6c7"
down_revision: str | None = "c7f2d3e4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_leave_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("periods_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("entitlements_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "auto_open_annual_period", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "relief_person_mode", sa.String(length=16), nullable=False, server_default="disabled"
        ),
        sa.Column(
            "approval_workflow", sa.String(length=32), nullable=False, server_default="manager"
        ),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_leave_policy_organization"),
    )
    op.create_index(
        "ix_organization_leave_policies_organization_id",
        "organization_leave_policies",
        ["organization_id"],
    )
    op.add_column("leave_requests", sa.Column("relief_person_id", sa.Uuid(), nullable=True))
    op.add_column(
        "leave_requests",
        sa.Column("approval_stage", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.create_foreign_key(
        "fk_leave_requests_relief_person_id_users",
        "leave_requests",
        "users",
        ["relief_person_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leave_requests_relief_person_id", "leave_requests", ["relief_person_id"])
    op.alter_column("leave_requests", "leave_period_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("leave_requests", "leave_period_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_leave_requests_relief_person_id", table_name="leave_requests")
    op.drop_constraint(
        "fk_leave_requests_relief_person_id_users", "leave_requests", type_="foreignkey"
    )
    op.drop_column("leave_requests", "approval_stage")
    op.drop_column("leave_requests", "relief_person_id")
    op.drop_index(
        "ix_organization_leave_policies_organization_id",
        table_name="organization_leave_policies",
    )
    op.drop_table("organization_leave_policies")
