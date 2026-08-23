"""Add notification center metadata and preferences.

Revision ID: 0021_notification_center
Revises: 0020_help_kms
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_notification_center"
down_revision: str | None = "0020_help_kms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("category", sa.String(48), nullable=False, server_default="general"),
    )
    op.add_column(
        "notifications",
        sa.Column("priority", sa.String(24), nullable=False, server_default="normal"),
    )
    op.add_column("notifications", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column(
        "notifications", sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_index("ix_notifications_category", "notifications", ["category"])
    op.create_index("ix_notifications_priority", "notifications", ["priority"])
    op.execute(
        "UPDATE notifications SET category = CASE "
        "WHEN notification_type LIKE 'meeting_%' THEN 'meetings' "
        "WHEN notification_type LIKE '%mention%' THEN 'mentions' "
        "WHEN notification_type LIKE '%approval%' THEN 'approvals' "
        "ELSE 'general' END"
    )
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("browser_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quiet_hours_start", sa.String(5)),
        sa.Column("quiet_hours_end", sa.String(5)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("category_rules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("delivery_rules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id"),
    )
    op.create_index(
        "ix_notification_preferences_organization_id",
        "notification_preferences",
        ["organization_id"],
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.execute("UPDATE menu_definitions SET enabled = TRUE WHERE key = 'notifications'")


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_priority", table_name="notifications")
    op.drop_index("ix_notifications_category", table_name="notifications")
    op.drop_column("notifications", "metadata")
    op.drop_column("notifications", "archived_at")
    op.drop_column("notifications", "priority")
    op.drop_column("notifications", "category")
