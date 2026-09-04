"""Backfill direct-conversation keys for existing MeetingHQ installations.

Revision ID: 0032_backfill_direct_member_keys
Revises: 0031_chat_push_notification_hardening
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032_backfill_direct_member_keys"
down_revision: str | None = "0031_chat_push_notification_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE conversations AS conversation
        SET direct_member_key = members.member_key
        FROM (
            SELECT conversation_id, string_agg(user_id::text, ':' ORDER BY user_id::text) AS member_key
            FROM conversation_members
            GROUP BY conversation_id
        ) AS members
        WHERE conversation.id = members.conversation_id
          AND conversation.type = 'direct'
          AND conversation.direct_member_key IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE conversations SET direct_member_key = NULL WHERE type = 'direct'"
    )
