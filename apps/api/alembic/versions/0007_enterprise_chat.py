"""Add enterprise chat and realtime collaboration.

Revision ID: 0007_chat
Revises: 0006_meetings
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_chat"
down_revision: str | None = "0006_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id")),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160)),
        sa.Column("description", sa.Text()),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="members"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
    )
    for column in ("organization_id", "workspace_id", "team_id", "archived_at"):
        op.create_index(f"ix_conversations_{column}", "conversations", [column])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_message_id", sa.Uuid(), sa.ForeignKey("messages.id")),
        sa.Column("message_type", sa.String(32), nullable=False, server_default="rich_text"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("conversation_id", "sender_id", "parent_message_id", "deleted_at", "created_at"):
        op.create_index(f"ix_messages_{column}", "messages", [column])
    op.create_index(
        "ix_messages_conversation_cursor",
        "messages",
        ["conversation_id", "created_at", "id"],
    )
    op.create_table(
        "conversation_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_read_message_id", sa.Uuid(), sa.ForeignKey("messages.id")),
        sa.Column("notification_preference", sa.String(24), nullable=False, server_default="all"),
        sa.UniqueConstraint("conversation_id", "user_id"),
    )
    op.create_index(
        "ix_conversation_members_conversation_id", "conversation_members", ["conversation_id"]
    )
    op.create_index("ix_conversation_members_user_id", "conversation_members", ["user_id"])
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column(
            "root_message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=False, unique=True
        ),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latest_reply_id", sa.Uuid(), sa.ForeignKey("messages.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_threads_conversation_id", "chat_threads", ["conversation_id"])
    op.create_table(
        "reactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("emoji", sa.String(64), nullable=False),
        sa.UniqueConstraint("message_id", "user_id", "emoji"),
    )
    op.create_index("ix_reactions_message_id", "reactions", ["message_id"])
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])
    op.create_table(
        "attachment_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_attachment_references_message_id", "attachment_references", ["message_id"])
    op.create_table(
        "pinned_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("pinned_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "message_id"),
    )
    op.create_index("ix_pinned_messages_conversation_id", "pinned_messages", ["conversation_id"])
    op.create_index("ix_pinned_messages_message_id", "pinned_messages", ["message_id"])
    op.create_table(
        "presence",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="offline"),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    permissions = (
        ("chat.read", "chat", "read", "Read conversations and messages"),
        ("chat.create", "chat", "create", "Create conversations and messages"),
        ("chat.edit", "chat", "edit", "Edit own messages"),
        ("chat.delete", "chat", "delete", "Delete own messages"),
        ("chat.manage", "chat", "manage", "Moderate enterprise chat"),
        ("channel.manage", "channel", "manage", "Manage channels"),
        ("conversation.manage", "conversation", "manage", "Manage conversations"),
    )
    connection = op.get_bind()
    for name, resource, action, description in permissions:
        permission_id = uuid.uuid4().hex
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id,name,resource,action,description) "
                "VALUES (:id,:name,:resource,:action,:description)"
            ),
            {
                "id": permission_id,
                "name": name,
                "resource": resource,
                "action": action,
                "description": description,
            },
        )
        roles = ["Super Admin", "Organization Admin", "Manager"]
        if name in {"chat.read", "chat.create", "chat.edit", "chat.delete"}:
            roles.append("Member")
        if name in {"chat.read", "chat.create"}:
            roles.append("Guest")
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id,permission_id) "
                "SELECT id,:permission_id FROM roles WHERE name IN :roles"
            ).bindparams(sa.bindparam("roles", expanding=True)),
            {"permission_id": permission_id, "roles": roles},
        )


def downgrade() -> None:
    connection = op.get_bind()
    names = [
        "chat.read",
        "chat.create",
        "chat.edit",
        "chat.delete",
        "chat.manage",
        "channel.manage",
        "conversation.manage",
    ]
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name IN :names)"
        ).bindparams(sa.bindparam("names", expanding=True)),
        {"names": names},
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE name IN :names").bindparams(
            sa.bindparam("names", expanding=True)
        ),
        {"names": names},
    )
    for table in (
        "presence",
        "pinned_messages",
        "attachment_references",
        "reactions",
        "chat_threads",
        "conversation_members",
        "messages",
        "conversations",
    ):
        op.drop_table(table)
