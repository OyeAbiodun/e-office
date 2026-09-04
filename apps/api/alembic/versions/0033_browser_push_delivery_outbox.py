"""Add a durable, tenant-scoped Web Push delivery outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0033_browser_push_delivery_outbox"
down_revision = "0032_backfill_direct_member_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "browser_push_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["push_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            "subscription_id",
            name="uq_browser_push_delivery_notification_subscription",
        ),
    )
    op.create_index(
        "ix_browser_push_deliveries_pending",
        "browser_push_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_browser_push_deliveries_notification_id",
        "browser_push_deliveries",
        ["notification_id"],
    )
    op.create_index(
        "ix_browser_push_deliveries_organization_id",
        "browser_push_deliveries",
        ["organization_id"],
    )
    op.create_index(
        "ix_browser_push_deliveries_subscription_id",
        "browser_push_deliveries",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_browser_push_deliveries_subscription_id", table_name="browser_push_deliveries"
    )
    op.drop_index(
        "ix_browser_push_deliveries_organization_id", table_name="browser_push_deliveries"
    )
    op.drop_index(
        "ix_browser_push_deliveries_notification_id", table_name="browser_push_deliveries"
    )
    op.drop_index("ix_browser_push_deliveries_pending", table_name="browser_push_deliveries")
    op.drop_table("browser_push_deliveries")
