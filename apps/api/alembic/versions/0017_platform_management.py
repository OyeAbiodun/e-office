"""Add configuration-driven features and navigation.

Revision ID: 0017_platform_management
Revises: 0016_meeting_mvp_delivery
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_platform_management"
down_revision: str | None = "0016_meeting_mvp_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("release_stage", sa.String(24), nullable=False, server_default="public"),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "key"),
    )
    op.create_index("ix_feature_flags_organization_id", "feature_flags", ["organization_id"])
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])
    op.create_table(
        "menu_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("path", sa.String(240), nullable=False),
        sa.Column("icon", sa.String(80), nullable=False, server_default="circle"),
        sa.Column("permission", sa.String(120), nullable=False),
        sa.Column("feature_key", sa.String(80)),
        sa.Column("badge", sa.String(40)),
        sa.Column("parent_key", sa.String(80)),
        sa.Column("section", sa.String(80), nullable=False, server_default="work"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "key"),
    )
    op.create_index("ix_menu_definitions_organization_id", "menu_definitions", ["organization_id"])
    op.create_index("ix_menu_definitions_key", "menu_definitions", ["key"])


def downgrade() -> None:
    op.drop_table("menu_definitions")
    op.drop_table("feature_flags")
