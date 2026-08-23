"""Add enterprise organization structure.

Revision ID: 0012_org_product
Revises: 0011_tenant_config
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012_org_product"
down_revision: str | None = "0011_tenant_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "organization_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("organization_units.id", ondelete="SET NULL"),
        ),
        sa.Column("unit_type", sa.String(24), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(40)),
        sa.Column("description", sa.String(1000)),
        sa.Column("address", json_type, nullable=False, server_default="{}"),
        sa.Column("timezone", sa.String(64)),
        sa.Column("working_hours", json_type, nullable=False, server_default="{}"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "unit_type", "code"),
    )
    for column in ("organization_id", "parent_id", "unit_type"):
        op.create_index(f"ix_organization_units_{column}", "organization_units", [column])


def downgrade() -> None:
    op.drop_table("organization_units")
