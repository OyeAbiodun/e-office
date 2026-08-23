"""Add tenant-isolated Internal Mail.

Revision ID: 0023_internal_mail
Revises: 0022_administration_centers
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_internal_mail"
down_revision: str | None = "0022_administration_centers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "mail_messages",
        *_identity_columns(),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.Uuid()),
        sa.Column("folder", sa.String(24), nullable=False, server_default="drafts"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("from_email", sa.String(320), nullable=False),
        sa.Column("from_name", sa.String(160), nullable=False),
        sa.Column("to_recipients", sa.JSON(), nullable=False),
        sa.Column("cc_recipients", sa.JSON(), nullable=False),
        sa.Column("bcc_recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.String(998), nullable=False, server_default=""),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("preview", sa.String(500), nullable=False, server_default=""),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_starred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "read_receipt_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("delivery_status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("delivery_error", sa.String(500)),
        sa.Column("reply_to_id", sa.Uuid()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("sender_id", "thread_id", "source_message_id", "folder", "status", "sent_at"):
        op.create_index(f"ix_mail_messages_{column}", "mail_messages", [column])
    op.create_table(
        "mail_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("mail_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for table, extra in (
        (
            "mail_folders",
            [
                sa.Column("name", sa.String(80), nullable=False),
                sa.Column("color", sa.String(20), nullable=False, server_default="#64748b"),
            ],
        ),
        (
            "mail_templates",
            [
                sa.Column("name", sa.String(120), nullable=False),
                sa.Column("subject", sa.String(998), nullable=False, server_default=""),
                sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            ],
        ),
        (
            "mail_signatures",
            [
                sa.Column("name", sa.String(120), nullable=False),
                sa.Column("body_html", sa.Text(), nullable=False),
                sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            ],
        ),
    ):
        op.create_table(
            table,
            *_identity_columns(),
            *extra,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.execute("UPDATE menu_definitions SET enabled = TRUE, hidden = FALSE WHERE key = 'mail'")


def downgrade() -> None:
    op.execute("UPDATE menu_definitions SET enabled = FALSE WHERE key = 'mail'")
    for table in ("mail_signatures", "mail_templates", "mail_folders", "mail_attachments"):
        op.drop_table(table)
    op.drop_table("mail_messages")
