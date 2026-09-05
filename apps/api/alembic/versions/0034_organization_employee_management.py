"""Add employment fields, history, and department stewardship."""

import sqlalchemy as sa
from alembic import op

revision = "0034_organization_employee_management"
down_revision = "0033_browser_push_delivery_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("alternative_phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("department_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("manager_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("employee_number", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "employment_status", sa.String(length=32), nullable=False, server_default="active"
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "employment_type", sa.String(length=32), nullable=False, server_default="permanent"
        ),
    )
    op.add_column("users", sa.Column("employment_start_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("employment_confirmation_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("employment_end_date", sa.Date(), nullable=True))
    op.create_foreign_key(
        "fk_users_department_id",
        "users",
        "organization_units",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_manager_id", "users", "users", ["manager_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_index("ix_users_manager_id", "users", ["manager_id"])
    op.create_index("ix_users_employee_number", "users", ["employee_number"])
    op.create_index("ix_users_employment_status", "users", ["employment_status"])
    op.create_index("ix_users_employment_type", "users", ["employment_type"])
    op.create_unique_constraint(
        "uq_users_org_employee_number", "users", ["organization_id", "employee_number"]
    )

    op.add_column("organization_units", sa.Column("manager_id", sa.Uuid(), nullable=True))
    op.add_column(
        "organization_units",
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
    )
    op.create_foreign_key(
        "fk_organization_units_manager_id",
        "organization_units",
        "users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_organization_units_manager_id", "organization_units", ["manager_id"])
    op.create_index("ix_organization_units_status", "organization_units", ["status"])

    op.create_table(
        "employment_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column("change_type", sa.String(length=48), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=False),
        sa.Column("new_values", sa.JSON(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employment_history_organization_id", "employment_history", ["organization_id"]
    )
    op.create_index("ix_employment_history_user_id", "employment_history", ["user_id"])
    op.create_index("ix_employment_history_changed_by", "employment_history", ["changed_by"])
    op.create_index(
        "ix_employment_history_effective_date", "employment_history", ["effective_date"]
    )
    op.create_index(
        "ix_employment_history_org_user_effective",
        "employment_history",
        ["organization_id", "user_id", "effective_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_employment_history_org_user_effective", table_name="employment_history")
    op.drop_index("ix_employment_history_effective_date", table_name="employment_history")
    op.drop_index("ix_employment_history_changed_by", table_name="employment_history")
    op.drop_index("ix_employment_history_user_id", table_name="employment_history")
    op.drop_index("ix_employment_history_organization_id", table_name="employment_history")
    op.drop_table("employment_history")
    op.drop_index("ix_organization_units_status", table_name="organization_units")
    op.drop_index("ix_organization_units_manager_id", table_name="organization_units")
    op.drop_constraint("fk_organization_units_manager_id", "organization_units", type_="foreignkey")
    op.drop_column("organization_units", "status")
    op.drop_column("organization_units", "manager_id")
    op.drop_constraint("uq_users_org_employee_number", "users", type_="unique")
    op.drop_index("ix_users_employment_type", table_name="users")
    op.drop_index("ix_users_employment_status", table_name="users")
    op.drop_index("ix_users_employee_number", table_name="users")
    op.drop_index("ix_users_manager_id", table_name="users")
    op.drop_index("ix_users_department_id", table_name="users")
    op.drop_constraint("fk_users_manager_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_department_id", "users", type_="foreignkey")
    op.drop_column("users", "employment_end_date")
    op.drop_column("users", "employment_confirmation_date")
    op.drop_column("users", "employment_start_date")
    op.drop_column("users", "employment_type")
    op.drop_column("users", "employment_status")
    op.drop_column("users", "employee_number")
    op.drop_column("users", "manager_id")
    op.drop_column("users", "department_id")
    op.drop_column("users", "alternative_phone")
