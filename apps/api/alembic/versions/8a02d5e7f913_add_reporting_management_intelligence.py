"""add reporting management intelligence

Revision ID: 8a02d5e7f913
Revises: 7f91c2d4e6ab
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8a02d5e7f913"
down_revision: str | None = "7f91c2d4e6ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("daily_enabled", sa.Boolean(), nullable=False),
        sa.Column("weekly_enabled", sa.Boolean(), nullable=False),
        sa.Column("monthly_enabled", sa.Boolean(), nullable=False),
        sa.Column("review_before_send", sa.Boolean(), nullable=False),
        sa.Column("automatic_submit", sa.Boolean(), nullable=False),
        sa.Column("week_start", sa.Integer(), nullable=False),
        sa.Column("week_end", sa.Integer(), nullable=False),
        sa.Column("generation_time", sa.Time(), nullable=False),
        sa.Column("submission_deadline_hours", sa.Integer(), nullable=False),
        sa.Column("manager_review_required", sa.Boolean(), nullable=False),
        sa.Column("reminder_hours_before", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("enabled_report_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_report_policy_org"),
    )
    op.create_index("ix_report_policies_organization_id", "report_policies", ["organization_id"])
    op.create_table(
        "generated_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("subject_type", sa.String(length=24), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("subject_name", sa.String(length=240), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("period_type", sa.String(length=24), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submission_mode", sa.String(length=16), nullable=True),
        sa.Column("generation_key", sa.String(length=300), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "authoritative_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("narrative", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "generation_key", name="uq_generated_reports_generation_key"
        ),
    )
    for name, columns in (
        ("ix_generated_reports_organization_id", ["organization_id"]),
        ("ix_generated_reports_report_type", ["report_type"]),
        ("ix_generated_reports_subject_type", ["subject_type"]),
        ("ix_generated_reports_subject_id", ["subject_id"]),
        ("ix_generated_reports_owner_id", ["owner_id"]),
        ("ix_generated_reports_manager_id", ["manager_id"]),
        ("ix_generated_reports_period_type", ["period_type"]),
        ("ix_generated_reports_period_start", ["period_start"]),
        ("ix_generated_reports_period_end", ["period_end"]),
        ("ix_generated_reports_status", ["status"]),
        (
            "ix_generated_reports_org_subject_period",
            ["organization_id", "subject_type", "subject_id", "period_start", "period_end"],
        ),
        ("ix_generated_reports_org_status_created", ["organization_id", "status", "created_at"]),
    ):
        op.create_index(name, "generated_reports", columns)
    op.create_table(
        "report_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("narrative", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["generated_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version", name="uq_report_versions_report_version"),
    )
    op.create_index("ix_report_versions_organization_id", "report_versions", ["organization_id"])
    op.create_index("ix_report_versions_report_id", "report_versions", ["report_id"])
    op.create_table(
        "report_review_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["generated_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_review_history_organization_id", "report_review_history", ["organization_id"]
    )
    op.create_index("ix_report_review_history_report_id", "report_review_history", ["report_id"])
    op.create_index("ix_report_review_history_action", "report_review_history", ["action"])
    op.create_index(
        "ix_report_review_history_report_created",
        "report_review_history",
        ["report_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("report_review_history")
    op.drop_table("report_versions")
    op.drop_table("generated_reports")
    op.drop_table("report_policies")
