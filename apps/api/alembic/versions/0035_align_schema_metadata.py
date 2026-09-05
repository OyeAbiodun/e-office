"""Align PostgreSQL indexes and JSON storage with mapped metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035_align_schema_metadata"
down_revision = "0034_organization_employee_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply metadata indexes and use JSONB for effective-dated history payloads."""
    op.create_index(
        "ix_browser_push_deliveries_next_attempt_at",
        "browser_push_deliveries",
        ["next_attempt_at"],
    )
    op.create_index(
        "ix_browser_push_deliveries_status",
        "browser_push_deliveries",
        ["status"],
    )
    op.create_index("ix_employment_history_change_type", "employment_history", ["change_type"])
    op.alter_column(
        "employment_history",
        "old_values",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="old_values::jsonb",
    )
    op.alter_column(
        "employment_history",
        "new_values",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="new_values::jsonb",
    )


def downgrade() -> None:
    """Revert schema alignment without changing history values."""
    op.alter_column(
        "employment_history",
        "new_values",
        existing_type=postgresql.JSONB(),
        type_=sa.JSON(),
        postgresql_using="new_values::json",
    )
    op.alter_column(
        "employment_history",
        "old_values",
        existing_type=postgresql.JSONB(),
        type_=sa.JSON(),
        postgresql_using="old_values::json",
    )
    op.drop_index("ix_employment_history_change_type", table_name="employment_history")
    op.drop_index("ix_browser_push_deliveries_status", table_name="browser_push_deliveries")
    op.drop_index(
        "ix_browser_push_deliveries_next_attempt_at",
        table_name="browser_push_deliveries",
    )
