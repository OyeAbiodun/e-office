"""Align high-volume query indexes with the persistence models.

Revision ID: 0027_query_index_alignment
Revises: 0026_release_delivery_hardening
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0027_query_index_alignment"
down_revision: str | None = "0026_release_delivery_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    ("ix_mail_messages_created_at", "mail_messages", "created_at"),
    ("ix_mail_messages_deleted_at", "mail_messages", "deleted_at"),
    ("ix_mail_messages_is_read", "mail_messages", "is_read"),
    ("ix_mail_messages_reply_to_id", "mail_messages", "reply_to_id"),
    (
        "ix_resource_reservations_start_datetime",
        "resource_reservations",
        "start_datetime",
    ),
    ("ix_resource_reservations_end_datetime", "resource_reservations", "end_datetime"),
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        # These tables can be large. Avoid blocking production writes while the indexes build.
        with context.autocommit_block():
            for name, table, column in INDEXES:
                op.execute(
                    f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" ON "{table}" ("{column}")'
                )
        return
    for name, table, column in INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "postgresql":
        with context.autocommit_block():
            for name, _, _ in reversed(INDEXES):
                op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"')
        return
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
