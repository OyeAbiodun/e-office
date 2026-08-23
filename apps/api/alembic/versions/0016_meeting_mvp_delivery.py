"""Add meeting invitation delivery, notifications, and reminders.

Revision ID: 0016_meeting_mvp_delivery
Revises: 0015_mvp_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016_meeting_mvp_delivery"
down_revision: str | None = "0015_mvp_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(
            sa.Column(
                "meeting_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "meetings.id",
                    name="fk_calendar_events_meeting_id_meetings",
                    ondelete="CASCADE",
                ),
            )
        )
    op.create_index("ix_calendar_events_meeting_id", "calendar_events", ["meeting_id"])
    with op.batch_alter_table("meetings") as batch:
        batch.add_column(sa.Column("agenda", sa.Text()))
        batch.add_column(sa.Column("location", sa.String(500)))
        batch.add_column(sa.Column("recurrence", json_type))
    op.create_index(
        "ux_meeting_attendees_meeting_user",
        "meeting_attendees",
        ["meeting_id", "user_id"],
        unique=True,
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
        ),
        sa.Column("notification_type", sa.String(48), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(1000)),
        sa.Column("delivered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    for column in ("organization_id", "user_id", "meeting_id", "notification_type"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])

    op.create_table(
        "meeting_invitation_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("transport_id", sa.String(240)),
        sa.Column("error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("meeting_id", "user_id", "channel"),
    )
    for column in ("organization_id", "meeting_id", "user_id", "status"):
        op.create_index(
            f"ix_meeting_invitation_deliveries_{column}",
            "meeting_invitation_deliveries",
            [column],
        )

    op.create_table(
        "meeting_reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            sa.Uuid(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.UniqueConstraint("meeting_id", "user_id", "offset_minutes"),
    )
    for column in ("organization_id", "meeting_id", "user_id", "scheduled_for", "status"):
        op.create_index(
            f"ix_meeting_reminders_{column}",
            "meeting_reminders",
            [column],
        )


def downgrade() -> None:
    op.drop_table("meeting_reminders")
    op.drop_table("meeting_invitation_deliveries")
    op.drop_table("notifications")
    op.drop_index(
        "ux_meeting_attendees_meeting_user",
        table_name="meeting_attendees",
    )
    with op.batch_alter_table("meetings") as batch:
        batch.drop_column("recurrence")
        batch.drop_column("location")
        batch.drop_column("agenda")
    op.drop_index("ix_calendar_events_meeting_id", table_name="calendar_events")
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_column("meeting_id")
