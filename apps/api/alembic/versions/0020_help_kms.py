"""Evolve Help Center into a tenant knowledge management system.

Revision ID: 0020_help_kms
Revises: 0019_help_center
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_help_kms"
down_revision: str | None = "0019_help_center"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "help_articles",
        sa.Column("workflow_status", sa.String(24), nullable=False, server_default="published"),
    )
    op.add_column(
        "help_articles",
        sa.Column("search_weight", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "help_articles", sa.Column("context_ids", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "help_articles", sa.Column("related_slugs", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column("help_articles", sa.Column("video_metadata", sa.JSON()))
    op.create_index("ix_help_articles_workflow_status", "help_articles", ["workflow_status"])

    op.create_table(
        "help_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("help_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("url", sa.String(1600), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_help_attachments_organization_id", "help_attachments", ["organization_id"])
    op.create_index("ix_help_attachments_article_id", "help_attachments", ["article_id"])

    op.create_table(
        "help_interactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("help_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("article_id", "user_id"),
    )
    op.create_index(
        "ix_help_interactions_organization_id",
        "help_interactions",
        ["organization_id"],
    )
    op.create_index("ix_help_interactions_article_id", "help_interactions", ["article_id"])
    op.create_index("ix_help_interactions_user_id", "help_interactions", ["user_id"])

    op.create_table(
        "product_tours",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("context_id", sa.String(180), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "context_id", "version"),
    )
    op.create_index("ix_product_tours_organization_id", "product_tours", ["organization_id"])
    op.create_index("ix_product_tours_context_id", "product_tours", ["context_id"])


def downgrade() -> None:
    op.drop_table("product_tours")
    op.drop_table("help_interactions")
    op.drop_table("help_attachments")
    op.drop_index("ix_help_articles_workflow_status", table_name="help_articles")
    op.drop_column("help_articles", "video_metadata")
    op.drop_column("help_articles", "related_slugs")
    op.drop_column("help_articles", "context_ids")
    op.drop_column("help_articles", "search_weight")
    op.drop_column("help_articles", "workflow_status")
