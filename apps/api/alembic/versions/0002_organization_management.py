"""Add organization management, teams, invitations, activity, and preferences.

Revision ID: 0002_org_management
Revises: 0001_identity
Create Date: 2026-08-01
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_org_management"
down_revision: str | Sequence[str] | None = "0001_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Expand tenant configuration and create collaboration hierarchy tables."""
    op.add_column(
        "organizations",
        sa.Column("brand_color", sa.String(7), nullable=False, server_default="#2563eb"),
    )
    op.add_column(
        "organizations",
        sa.Column("settings", json_type, nullable=False, server_default="{}"),
    )
    op.add_column("organizations", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.add_column("workspaces", sa.Column("logo_url", sa.String(2048)))
    op.add_column("workspaces", sa.Column("brand_color", sa.String(7)))
    op.add_column(
        "workspaces",
        sa.Column("settings", json_type, nullable=False, server_default="{}"),
    )
    op.add_column("workspaces", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC")
    )
    op.add_column(
        "users", sa.Column("language", sa.String(10), nullable=False, server_default="en")
    )
    op.add_column(
        "users",
        sa.Column("notification_preferences", json_type, nullable=False, server_default="{}"),
    )
    op.add_column("users", sa.Column("removed_at", sa.DateTime(timezone=True)))

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("resource", sa.String()),
        sa.column("action", sa.String()),
        sa.column("description", sa.String()),
    )
    definitions = (
        ("organizations.read", "organizations", "read", "View organization"),
        ("organizations.write", "organizations", "write", "Manage organization"),
        ("workspaces.read", "workspaces", "read", "View workspaces"),
        ("workspaces.write", "workspaces", "write", "Manage workspaces"),
        ("teams.read", "teams", "read", "View teams"),
        ("teams.write", "teams", "write", "Manage teams"),
        ("invitations.read", "invitations", "read", "View invitations"),
        ("invitations.write", "invitations", "write", "Manage invitations"),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "resource": resource,
                "action": action,
                "description": description,
            }
            for name, resource, action, description in definitions
        ],
    )
    connection = op.get_bind()
    for role_name, permission_names in {
        "Super Admin": [item[0] for item in definitions],
        "Organization Admin": [item[0] for item in definitions],
        "Manager": [
            "organizations.read",
            "workspaces.read",
            "workspaces.write",
            "teams.read",
            "teams.write",
            "invitations.read",
            "invitations.write",
        ],
        "Member": [
            "organizations.read",
            "workspaces.read",
            "teams.read",
            "teams.write",
        ],
        "Guest": ["organizations.read", "workspaces.read", "teams.read"],
    }.items():
        for permission_name in permission_names:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT roles.id, permissions.id FROM roles, permissions "
                    "WHERE roles.name = :role_name AND permissions.name = :permission_name"
                ),
                {"role_name": role_name, "permission_name": permission_name},
            )

    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("icon", sa.String(80)),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug"),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])
    op.create_index("ix_teams_workspace_id", "teams", ["workspace_id"])
    op.create_table(
        "team_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "user_id"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role_name", sa.String(80), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "invited_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "accepted_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("resend_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"])
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        ),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", sa.Uuid()),
        sa.Column("payload", json_type, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_events_organization_id", "activity_events", ["organization_id"])
    op.create_index("ix_activity_events_workspace_id", "activity_events", ["workspace_id"])
    op.create_index("ix_activity_events_actor_id", "activity_events", ["actor_id"])
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])
    op.create_index("ix_activity_events_occurred_at", "activity_events", ["occurred_at"])


def downgrade() -> None:
    """Remove organization management schema additions."""
    for table in ("activity_events", "invitations", "team_members", "teams"):
        op.drop_table(table)
    for table, columns in (
        ("users", ("removed_at", "notification_preferences", "language", "timezone")),
        ("workspaces", ("archived_at", "settings", "brand_color", "logo_url")),
        ("organizations", ("deleted_at", "settings", "brand_color")),
    ):
        for column in columns:
            op.drop_column(table, column)
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE name IN "
            "('organizations.read','organizations.write','workspaces.read',"
            "'workspaces.write','teams.read','teams.write',"
            "'invitations.read','invitations.write')"
        )
    )
