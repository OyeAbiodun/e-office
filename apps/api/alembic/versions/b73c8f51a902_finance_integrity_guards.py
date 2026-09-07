"""Protect immutable ledger values and voucher monetary ordering.

Revision ID: b73c8f51a902
Revises: f3cb669e64ff
"""

from alembic import op

revision = "b73c8f51a902"
down_revision = "f3cb669e64ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vouchers") as batch:
        batch.create_check_constraint(
            "ck_vouchers_amount_order",
            "disbursed_amount <= approved_amount AND approved_amount <= requested_amount",
        )
    with op.batch_alter_table("finance_transactions") as batch:
        batch.create_check_constraint(
            "ck_finance_transactions_direction", "direction IN ('credit', 'debit')"
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION meetinghq_guard_ledger() RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'Ledger records cannot be deleted';
                END IF;
                IF (to_jsonb(NEW) - ARRAY['reconciled','reconciled_at',
                    'reconciliation_reference','reconciliation_note'])
                   IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['reconciled','reconciled_at',
                    'reconciliation_reference','reconciliation_note']) THEN
                    RAISE EXCEPTION 'Ledger values are immutable; post a reversal';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """
        )
        op.execute(
            """
            CREATE TRIGGER meetinghq_immutable_ledger
            BEFORE UPDATE OR DELETE ON finance_transactions
            FOR EACH ROW EXECUTE FUNCTION meetinghq_guard_ledger()
        """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER meetinghq_immutable_ledger ON finance_transactions")
        op.execute("DROP FUNCTION meetinghq_guard_ledger()")
    with op.batch_alter_table("finance_transactions") as batch:
        batch.drop_constraint("ck_finance_transactions_direction", type_="check")
    with op.batch_alter_table("vouchers") as batch:
        batch.drop_constraint("ck_vouchers_amount_order", type_="check")
