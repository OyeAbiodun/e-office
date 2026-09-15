"""add OfficeFlow support requests

Revision ID: 9b13e6f8a024
Revises: 8a02d5e7f913
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b13e6f8a024"
down_revision: str | None = "8a02d5e7f913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(length=32), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("page_url", sa.String(length=1000), nullable=True),
        sa.Column("module", sa.String(length=120), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "reference"),
    )
    op.create_index("ix_support_requests_organization_id", "support_requests", ["organization_id"])
    op.create_index("ix_support_requests_requester_id", "support_requests", ["requester_id"])
    op.create_index("ix_support_requests_reference", "support_requests", ["reference"])
    op.create_index("ix_support_requests_request_type", "support_requests", ["request_type"])
    op.create_index("ix_support_requests_priority", "support_requests", ["priority"])
    op.create_index("ix_support_requests_status", "support_requests", ["status"])
    op.create_index("ix_support_requests_module", "support_requests", ["module"])
    op.create_index("ix_support_requests_created_at", "support_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("support_requests")
