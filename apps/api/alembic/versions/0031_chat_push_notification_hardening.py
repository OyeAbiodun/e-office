"""Add idempotent chat sends and browser push subscription storage.

Revision ID: 0031_chat_push_notification_hardening
Revises: 0030_email_calendar_delivery_integrity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_chat_push_notification_hardening"
down_revision: str | None = "0030_email_calendar_delivery_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("direct_member_key", sa.String(80)))
    op.execute(
        """
        UPDATE conversations AS conversation
        SET direct_member_key = members.member_key
        FROM (
            SELECT conversation_id, string_agg(user_id::text, ':' ORDER BY user_id::text) AS member_key
            FROM conversation_members
            GROUP BY conversation_id
        ) AS members
        WHERE conversation.id = members.conversation_id AND conversation.type = 'direct'
        """
    )
    op.create_unique_constraint(
        "uq_conversations_direct_members",
        "conversations",
        ["organization_id", "direct_member_key"],
    )
    op.add_column("messages", sa.Column("client_message_id", sa.Uuid()))
    op.create_index("ix_messages_client_message_id", "messages", ["client_message_id"])
    op.create_unique_constraint(
        "uq_messages_conversation_sender_client",
        "messages",
        ["conversation_id", "sender_id", "client_message_id"],
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(2048), nullable=False),
        sa.Column("p256dh", sa.String(512), nullable=False),
        sa.Column("auth", sa.String(512), nullable=False),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "endpoint", name="uq_push_subscription_endpoint"),
    )
    op.create_index("ix_push_subscriptions_organization_id", "push_subscriptions", ["organization_id"])
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index(
        "ix_push_subscriptions_user_enabled",
        "push_subscriptions",
        ["organization_id", "user_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_enabled", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_organization_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_constraint("uq_messages_conversation_sender_client", "messages", type_="unique")
    op.drop_index("ix_messages_client_message_id", table_name="messages")
    op.drop_column("messages", "client_message_id")
    op.drop_constraint("uq_conversations_direct_members", "conversations", type_="unique")
    op.drop_column("conversations", "direct_member_key")
