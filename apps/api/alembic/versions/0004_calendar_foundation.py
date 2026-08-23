"""Add calendar foundation and scheduling resources.

Revision ID: 0004_calendar
Revises: 0003_architecture
"""

# ruff: noqa: E501

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004_calendar"
down_revision: str | None = "0003_architecture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "calendars",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id")),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id")),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("color", sa.String(7), nullable=False, server_default="#2563eb"),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="members"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("organization_id", "workspace_id", "team_id", "owner_id"):
        op.create_index(f"ix_calendars_{column}", "calendars", [column])
    op.create_table(
        "recurrence_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("frequency", sa.String(24), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("days_of_week", json_type, nullable=False, server_default="[]"),
        sa.Column("end_date", sa.Date()),
        sa.Column("occurrence_count", sa.Integer()),
        sa.Column("exception_dates", json_type, nullable=False, server_default="[]"),
        sa.Column("skip_holidays", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("calendar_id", sa.Uuid(), sa.ForeignKey("calendars.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="confirmed"),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="members"),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recurrence_rule_id", sa.Uuid(), sa.ForeignKey("recurrence_rules.id")),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("calendar_id", "start_datetime", "end_datetime"):
        op.create_index(f"ix_calendar_events_{column}", "calendar_events", [column])
    op.create_table(
        "availability_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("calendar_id", sa.Uuid(), sa.ForeignKey("calendars.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("availability_type", sa.String(40), nullable=False, server_default="available"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("calendar_id", "weekday", "start_time", "end_time"),
    )
    op.create_index("ix_availability_rules_calendar_id", "availability_rules", ["calendar_id"])
    op.create_table(
        "holidays",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", "name", "date"),
    )
    op.create_index("ix_holidays_organization_id", "holidays", ["organization_id"])
    op.create_index("ix_holidays_date", "holidays", ["date"])
    op.create_table(
        "busy_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("calendar_id", sa.Uuid(), sa.ForeignKey("calendars.id"), nullable=False),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(240)),
    )
    for column in ("calendar_id", "start_datetime", "end_datetime"):
        op.create_index(f"ix_busy_blocks_{column}", "busy_blocks", [column])
    op.create_table(
        "resources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "calendar_id", sa.Uuid(), sa.ForeignKey("calendars.id"), nullable=False, unique=True
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("location", sa.String(240)),
        sa.Column("status", sa.String(24), nullable=False, server_default="available"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
    )
    op.create_index("ix_resources_organization_id", "resources", ["organization_id"])
    op.create_index("ix_resources_workspace_id", "resources", ["workspace_id"])
    op.create_table(
        "resource_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("resource_id", sa.Uuid(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column(
            "calendar_event_id", sa.Uuid(), sa.ForeignKey("calendar_events.id"), nullable=False
        ),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("resource_id", "calendar_event_id"),
    )
    op.create_index(
        "ix_resource_reservations_resource_id", "resource_reservations", ["resource_id"]
    )
    op.create_index(
        "ix_resource_reservations_calendar_event_id", "resource_reservations", ["calendar_event_id"]
    )

    permissions = (
        ("calendar.write", "calendar", "write", "Create and update calendars"),
        ("calendar.manage", "calendar", "manage", "Manage calendar lifecycle"),
        ("resource.manage", "resource", "manage", "Manage scheduling resources"),
        ("holiday.manage", "holiday", "manage", "Manage organization holidays"),
        ("availability.manage", "availability", "manage", "Manage availability"),
    )
    table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    op.bulk_insert(
        table,
        [
            {"id": uuid.uuid4(), "name": n, "resource": r, "action": a, "description": d}
            for n, r, a, d in permissions
        ],
    )
    connection = op.get_bind()
    role_map = {
        "Super Admin": [item[0] for item in permissions],
        "Organization Admin": [item[0] for item in permissions],
        "Manager": [item[0] for item in permissions],
        "Member": ["calendar.write", "availability.manage"],
    }
    for role, names in role_map.items():
        for name in names:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT roles.id, permissions.id FROM roles, permissions "
                    "WHERE roles.name=:role AND permissions.name=:permission"
                ),
                {"role": role, "permission": name},
            )


def downgrade() -> None:
    for table in (
        "resource_reservations",
        "resources",
        "busy_blocks",
        "holidays",
        "availability_rules",
        "calendar_events",
        "recurrence_rules",
        "calendars",
    ):
        op.drop_table(table)
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE name IN "
            "('calendar.write','calendar.manage','resource.manage','holiday.manage','availability.manage')"
        )
    )
