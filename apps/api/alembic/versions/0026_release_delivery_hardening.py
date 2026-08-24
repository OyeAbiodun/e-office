"""Persist retry state for outbound delivery pipelines.

Revision ID: 0026_release_delivery_hardening
Revises: 0025_profile_center_completion
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_release_delivery_hardening"
down_revision: str | None = "0025_profile_center_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("meeting_invitation_deliveries", "meeting_reminders"):
        op.add_column(
            table,
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.add_column(table, sa.Column("last_attempt_at", sa.DateTime(timezone=True)))
        op.add_column(table, sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
        op.create_index(f"ix_{table}_next_attempt_at", table, ["next_attempt_at"])

    op.add_column(
        "mail_messages",
        sa.Column("delivery_attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "mail_messages", sa.Column("delivery_last_attempt_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "mail_messages", sa.Column("delivery_next_attempt_at", sa.DateTime(timezone=True))
    )
    op.create_index(
        "ix_mail_messages_delivery_next_attempt_at",
        "mail_messages",
        ["delivery_next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mail_messages_delivery_next_attempt_at", table_name="mail_messages")
    op.drop_column("mail_messages", "delivery_next_attempt_at")
    op.drop_column("mail_messages", "delivery_last_attempt_at")
    op.drop_column("mail_messages", "delivery_attempt_count")

    for table in ("meeting_reminders", "meeting_invitation_deliveries"):
        op.drop_index(f"ix_{table}_next_attempt_at", table_name=table)
        op.drop_column(table, "next_attempt_at")
        op.drop_column(table, "last_attempt_at")
        op.drop_column(table, "attempt_count")
