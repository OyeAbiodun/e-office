"""Complete calendar collaboration persistence.

Revision ID: 0008_calendar
Revises: 0007_chat
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_calendar"
down_revision: str | None = "0007_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name"),
    )
    op.create_index(
        "ix_event_categories_organization_id",
        "event_categories",
        ["organization_id"],
    )
    op.create_table(
        "calendar_shares",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("calendar_id", sa.Uuid(), sa.ForeignKey("calendars.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permission", sa.String(24), nullable=False, server_default="read"),
        sa.Column("shared_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("calendar_id", "user_id"),
    )
    op.create_index("ix_calendar_shares_calendar_id", "calendar_shares", ["calendar_id"])
    op.create_index("ix_calendar_shares_user_id", "calendar_shares", ["user_id"])
    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(sa.Column("recurrence_parent_id", sa.Uuid()))
        batch.add_column(sa.Column("original_start_datetime", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("category_id", sa.Uuid()))
        batch.create_foreign_key(
            "fk_calendar_events_recurrence_parent_id",
            "calendar_events",
            ["recurrence_parent_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_calendar_events_category_id",
            "event_categories",
            ["category_id"],
            ["id"],
        )
        batch.create_index("ix_calendar_events_recurrence_parent_id", ["recurrence_parent_id"])
        batch.create_index("ix_calendar_events_category_id", ["category_id"])


def downgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_index("ix_calendar_events_category_id")
        batch.drop_index("ix_calendar_events_recurrence_parent_id")
        batch.drop_constraint("fk_calendar_events_category_id", type_="foreignkey")
        batch.drop_constraint("fk_calendar_events_recurrence_parent_id", type_="foreignkey")
        batch.drop_column("category_id")
        batch.drop_column("original_start_datetime")
        batch.drop_column("recurrence_parent_id")
    op.drop_index("ix_calendar_shares_user_id", table_name="calendar_shares")
    op.drop_index("ix_calendar_shares_calendar_id", table_name="calendar_shares")
    op.drop_table("calendar_shares")
    op.drop_index("ix_event_categories_organization_id", table_name="event_categories")
    op.drop_table("event_categories")
