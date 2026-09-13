"""add project management

Revision ID: 7f91c2d4e6ab
Revises: 0a7d34f129cd
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7f91c2d4e6ab"
down_revision: str | Sequence[str] | None = "0a7d34f129cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def common_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("project_code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_manager_id", sa.Uuid(), nullable=False),
        sa.Column("sponsor_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_end_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False),
        sa.Column("health", sa.String(24), nullable=False),
        sa.Column("manual_progress", sa.Integer(), nullable=True),
        sa.Column("progress_mode", sa.String(24), nullable=False),
        sa.Column("visibility", sa.String(24), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_manager_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sponsor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["organization_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "project_code", name="uq_projects_org_code"),
    )
    op.create_index(
        "ix_projects_org_status_health", "projects", ["organization_id", "status", "health"]
    )
    op.create_index(
        "ix_projects_org_manager_end",
        "projects",
        ["organization_id", "project_manager_id", "target_end_date"],
    )
    for column in (
        "organization_id",
        "project_manager_id",
        "sponsor_id",
        "department_id",
        "team_id",
        "target_end_date",
        "status",
        "priority",
        "health",
        "visibility",
        "archived_at",
    ):
        op.create_index(op.f(f"ix_projects_{column}"), "projects", [column])

    op.create_table(
        "project_members",
        *common_columns(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("added_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )
    op.create_index(
        "ix_project_members_org_user", "project_members", ["organization_id", "user_id"]
    )
    op.create_index(op.f("ix_project_members_project_id"), "project_members", ["project_id"])
    op.create_index(
        op.f("ix_project_members_organization_id"), "project_members", ["organization_id"]
    )
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"])

    op.create_table(
        "project_milestones",
        *common_columns(),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_project_milestones_project_name"),
    )
    op.create_index(
        "ix_project_milestones_project_order", "project_milestones", ["project_id", "sequence"]
    )
    for column in ("organization_id", "project_id", "target_date", "status", "owner_id"):
        op.create_index(op.f(f"ix_project_milestones_{column}"), "project_milestones", [column])

    op.create_table(
        "project_updates",
        *common_columns(),
        sa.Column("reporting_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("accomplishments", sa.Text(), nullable=True),
        sa.Column("current_status", sa.Text(), nullable=True),
        sa.Column("blockers", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_updates_project_date", "project_updates", ["project_id", "reporting_date"]
    )
    op.create_index(
        op.f("ix_project_updates_organization_id"), "project_updates", ["organization_id"]
    )
    op.create_index(op.f("ix_project_updates_project_id"), "project_updates", ["project_id"])
    op.create_index(
        op.f("ix_project_updates_reporting_date"), "project_updates", ["reporting_date"]
    )

    for table, date_column in (("project_risks", "review_date"), ("project_issues", "due_date")):
        columns = [
            *common_columns(),
            sa.Column("title", sa.String(240), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
        ]
        if table == "project_risks":
            columns += [
                sa.Column("probability", sa.String(16), nullable=False),
                sa.Column("impact", sa.String(16), nullable=False),
            ]
        columns += [
            sa.Column("severity", sa.String(16), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column(
                "mitigation" if table == "project_risks" else "resolution", sa.Text(), nullable=True
            ),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column(date_column, sa.Date(), nullable=True),
            sa.Column("created_by_id", sa.Uuid(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        ]
        op.create_table(table, *columns)
        op.create_index(f"ix_{table}_project_status", table, ["project_id", "status"])
        op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
        op.create_index(op.f(f"ix_{table}_project_id"), table, ["project_id"])
        op.create_index(op.f(f"ix_{table}_status"), table, ["status"])

    op.create_table(
        "project_attachments",
        *common_columns(),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_project_attachments_project_created",
        "project_attachments",
        ["project_id", "created_at"],
    )
    op.create_index(
        op.f("ix_project_attachments_organization_id"), "project_attachments", ["organization_id"]
    )
    op.create_index(
        op.f("ix_project_attachments_project_id"), "project_attachments", ["project_id"]
    )

    op.add_column("tasks", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("tasks", sa.Column("milestone_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_project_id", "tasks", "projects", ["project_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_tasks_milestone_id",
        "tasks",
        "project_milestones",
        ["milestone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"])
    op.create_index(op.f("ix_tasks_milestone_id"), "tasks", ["milestone_id"])
    op.add_column("daily_activities", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_daily_activities_project_id",
        "daily_activities",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_daily_activities_project_id"), "daily_activities", ["project_id"])
    op.add_column("meetings", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_meetings_project_id",
        "meetings",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_meetings_project_id"), "meetings", ["project_id"])


def downgrade() -> None:
    for table in ("meetings", "daily_activities"):
        op.drop_index(op.f(f"ix_{table}_project_id"), table_name=table)
        op.drop_constraint(f"fk_{table}_project_id", table, type_="foreignkey")
        op.drop_column(table, "project_id")
    op.drop_index(op.f("ix_tasks_milestone_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_project_id"), table_name="tasks")
    op.drop_constraint("fk_tasks_milestone_id", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_project_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "milestone_id")
    op.drop_column("tasks", "project_id")
    for table in (
        "project_attachments",
        "project_issues",
        "project_risks",
        "project_updates",
        "project_milestones",
        "project_members",
        "projects",
    ):
        op.drop_table(table)
