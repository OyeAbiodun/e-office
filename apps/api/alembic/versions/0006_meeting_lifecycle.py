"""Add meeting lifecycle and collaboration.

Revision ID: 0006_meetings
Revises: 0005_bootstrap
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_meetings"
down_revision: str | None = "0005_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "meeting_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("default_duration", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("default_visibility", sa.String(24), nullable=False, server_default="members"),
        sa.Column("default_agenda", json_type, nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_meeting_templates_organization_id", "meeting_templates", ["organization_id"]
    )
    op.create_table(
        "meetings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("calendar_event_id", sa.Uuid(), sa.ForeignKey("calendar_events.id"), unique=True),
        sa.Column("meeting_template_id", sa.Uuid(), sa.ForeignKey("meeting_templates.id")),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("meeting_type", sa.String(64), nullable=False, server_default="standard"),
        sa.Column("location_type", sa.String(32), nullable=False, server_default="virtual"),
        sa.Column("meeting_url", sa.String(1000)),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("resources.id")),
        sa.Column("organizer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="members"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in (
        "organization_id",
        "workspace_id",
        "organizer_id",
        "start_datetime",
        "end_datetime",
    ):
        op.create_index(f"ix_meetings_{column}", "meetings", [column])
    op.create_table(
        "meeting_attendees",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="attendee"),
        sa.Column("attendance_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("meeting_id", "user_id"),
    )
    op.create_index("ix_meeting_attendees_meeting_id", "meeting_attendees", ["meeting_id"])
    op.create_index("ix_meeting_attendees_user_id", "meeting_attendees", ["user_id"])
    op.create_table(
        "meeting_agendas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_meeting_agendas_meeting_id", "meeting_agendas", ["meeting_id"])
    op.create_table(
        "meeting_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="recorded"),
    )
    op.create_index("ix_meeting_decisions_meeting_id", "meeting_decisions", ["meeting_id"])
    op.create_table(
        "meeting_action_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("due_date", sa.Date()),
        sa.Column("priority", sa.String(24), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_meeting_action_items_meeting_id", "meeting_action_items", ["meeting_id"])
    op.create_index("ix_meeting_action_items_assigned_to", "meeting_action_items", ["assigned_to"])
    op.create_table(
        "meeting_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meeting_id", sa.Uuid(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meeting_notes_meeting_id", "meeting_notes", ["meeting_id"])
    op.create_index("ix_meeting_notes_author_id", "meeting_notes", ["author_id"])

    permissions = (
        ("meetings.read", "meetings", "read", "View meetings"),
        ("meetings.cancel", "meetings", "cancel", "Cancel meetings"),
        ("meetings.manage", "meetings", "manage", "Manage meeting lifecycle"),
        ("agenda.manage", "agenda", "manage", "Manage meeting agendas"),
        ("action.manage", "action", "manage", "Manage meeting action items"),
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
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id,permission_id) "
                "SELECT id,:permission_id FROM roles WHERE name IN "
                "('Super Admin','Organization Admin','Manager')"
            ),
            {"permission_id": permission_id},
        )
        if name in {"meetings.read", "agenda.manage", "action.manage"}:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id,permission_id) "
                    "SELECT id,:permission_id FROM roles WHERE name='Member'"
                ),
                {"permission_id": permission_id},
            )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name IN "
            "('meetings.read','meetings.cancel','meetings.manage','agenda.manage','action.manage'))"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE name IN "
            "('meetings.read','meetings.cancel','meetings.manage','agenda.manage','action.manage')"
        )
    )
    for table in (
        "meeting_notes",
        "meeting_action_items",
        "meeting_decisions",
        "meeting_agendas",
        "meeting_attendees",
        "meetings",
        "meeting_templates",
    ):
        op.drop_table(table)
