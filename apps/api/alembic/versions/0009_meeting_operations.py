"""Add meeting artifacts, recordings, attendance, controls, and follow-ups.

Revision ID: 0009_meetings
Revises: 0008_calendar
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0009_meetings"
down_revision: str | None = "0008_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "meeting_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False, server_default="attachment"),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("storage_key", sa.String(1000)),
        sa.Column("content_type", sa.String(160)),
        sa.Column("size", sa.BigInteger()),
        sa.Column("metadata_json", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meeting_artifacts_meeting_id", "meeting_artifacts", ["meeting_id"])
    op.create_table(
        "meeting_recordings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default="meetinghq"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.Column("storage_key", sa.String(1000)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column(
            "transcript_status",
            sa.String(32),
            nullable=False,
            server_default="not_requested",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meeting_recordings_meeting_id", "meeting_recordings", ["meeting_id"])
    op.create_table(
        "meeting_attendance_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("recorded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_meeting_attendance_events_meeting_id",
        "meeting_attendance_events",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_attendance_events_user_id",
        "meeting_attendance_events",
        ["user_id"],
    )
    op.create_table(
        "meeting_presenter_controls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("control", sa.String(32), nullable=False),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_meeting_presenter_controls_meeting_id",
        "meeting_presenter_controls",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_presenter_controls_user_id",
        "meeting_presenter_controls",
        ["user_id"],
    )
    op.create_table(
        "meeting_follow_ups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("follow_up_type", sa.String(48), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("payload", json_type, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meeting_follow_ups_meeting_id", "meeting_follow_ups", ["meeting_id"])
    op.create_index("ix_meeting_follow_ups_scheduled_for", "meeting_follow_ups", ["scheduled_for"])


def downgrade() -> None:
    for table in (
        "meeting_follow_ups",
        "meeting_presenter_controls",
        "meeting_attendance_events",
        "meeting_recordings",
        "meeting_artifacts",
    ):
        op.drop_table(table)
