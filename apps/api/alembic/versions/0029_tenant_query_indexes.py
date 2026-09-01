"""Add tenant-first cursor and unread query indexes.

Revision ID: 0029_tenant_query_indexes
Revises: 0028_postgres_alignment
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_tenant_query_indexes"
down_revision: str | None = "0028_postgres_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    (
        "ix_meetings_org_start_cursor",
        "meetings",
        ["organization_id", "start_datetime", "id"],
    ),
    (
        "ix_notifications_org_user_delivery_cursor",
        "notifications",
        ["organization_id", "user_id", "delivered_at", "id"],
    ),
    (
        "ix_notifications_org_user_unread",
        "notifications",
        ["organization_id", "user_id", "read_at", "archived_at"],
    ),
    (
        "ix_audit_logs_org_created_cursor",
        "audit_logs",
        ["organization_id", "created_at", "id"],
    ),
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        with context.autocommit_block():
            for name, table, columns in INDEXES:
                op.create_index(
                    name,
                    table,
                    columns,
                    postgresql_concurrently=True,
                )
        return
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        with context.autocommit_block():
            for name, table, _ in reversed(INDEXES):
                op.drop_index(name, table_name=table, postgresql_concurrently=True)
        return
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
