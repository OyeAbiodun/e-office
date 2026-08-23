"""Add Teams-style channel tabs, drafts, and saved messages.

Revision ID: 0010_teams_channels
Revises: 0009_meetings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_teams_channels"
down_revision: str | None = "0009_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(
            sa.Column(
                "channel_kind",
                sa.String(24),
                nullable=False,
                server_default="standard",
            )
        )
    op.create_table(
        "channel_tabs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("tab_type", sa.String(32), nullable=False),
        sa.Column("configuration", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "name"),
    )
    op.create_index("ix_channel_tabs_conversation_id", "channel_tabs", ["conversation_id"])
    op.create_table(
        "saved_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("saved_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "message_id"),
    )
    op.create_index("ix_saved_messages_user_id", "saved_messages", ["user_id"])
    op.create_index("ix_saved_messages_message_id", "saved_messages", ["message_id"])
    op.create_table(
        "message_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "user_id"),
    )
    op.create_index("ix_message_drafts_conversation_id", "message_drafts", ["conversation_id"])
    op.create_index("ix_message_drafts_user_id", "message_drafts", ["user_id"])


def downgrade() -> None:
    op.drop_table("message_drafts")
    op.drop_table("saved_messages")
    op.drop_table("channel_tabs")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("channel_kind")
