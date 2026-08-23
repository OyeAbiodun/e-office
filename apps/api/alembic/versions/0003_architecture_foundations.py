"""Add extensible architecture foundations.

Revision ID: 0003_architecture
Revises: 0002_org_management
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_architecture"
down_revision: str | None = "0002_org_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add event, audit, configuration, and attributed soft-delete storage."""
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    for table in ("organizations", "workspaces", "teams"):
        if table != "organizations":
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("deleted_by", sa.Uuid()))

    op.create_table(
        "configuration_entries",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("value", json_type, nullable=False, server_default="{}"),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_configuration_entries_category", "configuration_entries", ["category"])
    op.create_table(
        "domain_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id")),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("name", "organization_id", "workspace_id"):
        op.create_index(f"ix_domain_events_{column}", "domain_events", [column])
    op.add_column("audit_logs", sa.Column("resource_id", sa.Uuid()))
    op.add_column("audit_logs", sa.Column("request_id", sa.String(80)))
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(64)))


def downgrade() -> None:
    """Remove architecture foundation storage."""
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "resource_id")
    op.drop_table("domain_events")
    op.drop_table("configuration_entries")
    for table in ("teams", "workspaces"):
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "deleted_by")
    op.drop_column("organizations", "deleted_by")
