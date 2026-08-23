"""Add production capability governance metadata.

Revision ID: 0024_capability_governance
Revises: 0023_internal_mail
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_capability_governance"
down_revision: str | None = "0023_internal_mail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_flags",
        sa.Column(
            "availability_status",
            sa.String(length=24),
            nullable=False,
            server_default="available",
        ),
    )
    op.add_column(
        "feature_flags",
        sa.Column(
            "implementation_status",
            sa.String(length=120),
            nullable=False,
            server_default="Implemented",
        ),
    )
    op.add_column("feature_flags", sa.Column("planned_version", sa.String(length=40)))
    op.add_column("feature_flags", sa.Column("estimated_availability", sa.String(length=80)))
    op.add_column(
        "feature_flags",
        sa.Column(
            "dependencies",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column("feature_flags", sa.Column("navigation_path", sa.String(length=240)))
    op.add_column("feature_flags", sa.Column("documentation_path", sa.String(length=240)))
    for column in (
        "ui_available",
        "backend_available",
        "navigation_available",
        "search_available",
        "permissions_available",
        "installed",
    ):
        op.add_column(
            "feature_flags",
            sa.Column(
                column,
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    op.create_table(
        "system_health_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "summary",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_health_snapshots_organization_id",
        "system_health_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_system_health_snapshots_checked_at",
        "system_health_snapshots",
        ["checked_at"],
    )
    op.create_table(
        "user_profile_centers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cover_image_url", sa.String(length=2048)),
        sa.Column("presence", sa.String(length=24), nullable=False),
        sa.Column("status_message", sa.String(length=240)),
        sa.Column("manager_id", sa.Uuid()),
        sa.Column("emergency_contact", sa.JSON(), nullable=False),
        sa.Column("email_aliases", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(length=4000)),
        sa.Column("working_hours", sa.JSON(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("connected_accounts", sa.JSON(), nullable=False),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False),
        sa.Column("mfa_secret", sa.JSON()),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False),
        sa.Column("storage_used_bytes", sa.Integer(), nullable=False),
        sa.Column("license_name", sa.String(length=80), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_user_profile_centers_organization_id",
        "user_profile_centers",
        ["organization_id"],
    )
    op.create_index(
        "ix_user_profile_centers_user_id",
        "user_profile_centers",
        ["user_id"],
    )
    op.create_index(
        "ix_user_profile_centers_manager_id",
        "user_profile_centers",
        ["manager_id"],
    )
    op.create_table(
        "user_api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_user_api_tokens_organization_id",
        "user_api_tokens",
        ["organization_id"],
    )
    op.create_index("ix_user_api_tokens_user_id", "user_api_tokens", ["user_id"])
    op.create_index(
        "ix_user_api_tokens_token_hash",
        "user_api_tokens",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_api_tokens_token_hash", table_name="user_api_tokens")
    op.drop_index("ix_user_api_tokens_user_id", table_name="user_api_tokens")
    op.drop_index("ix_user_api_tokens_organization_id", table_name="user_api_tokens")
    op.drop_table("user_api_tokens")
    op.drop_index("ix_user_profile_centers_manager_id", table_name="user_profile_centers")
    op.drop_index("ix_user_profile_centers_user_id", table_name="user_profile_centers")
    op.drop_index(
        "ix_user_profile_centers_organization_id",
        table_name="user_profile_centers",
    )
    op.drop_table("user_profile_centers")
    op.drop_index(
        "ix_system_health_snapshots_checked_at",
        table_name="system_health_snapshots",
    )
    op.drop_index(
        "ix_system_health_snapshots_organization_id",
        table_name="system_health_snapshots",
    )
    op.drop_table("system_health_snapshots")
    for column in (
        "installed",
        "permissions_available",
        "search_available",
        "navigation_available",
        "backend_available",
        "ui_available",
        "documentation_path",
        "navigation_path",
        "dependencies",
        "estimated_availability",
        "planned_version",
        "implementation_status",
        "availability_status",
    ):
        op.drop_column("feature_flags", column)
