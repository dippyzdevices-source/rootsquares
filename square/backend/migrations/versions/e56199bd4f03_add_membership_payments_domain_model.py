"""add membership payments domain model

Revision ID: e56199bd4f03
Revises: 747e3c1cc077
Create Date: 2026-09-11 10:20:25.220386

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column, String


# revision identifiers, used by Alembic.
revision = 'e56199bd4f03'
down_revision = '747e3c1cc077'
branch_labels = None
depends_on = None


def upgrade():
    # payments: new payment_type column, backfilled before being made NOT NULL so the one
    # pre-existing row (and any other legacy row) gets a valid value.
    op.add_column("payments", sa.Column("payment_type", sa.String(length=20), nullable=True))
    payments_table = table("payments", column("payment_type", String))
    op.execute(payments_table.update().values(payment_type="event_ticket"))
    op.alter_column("payments", "payment_type", nullable=False)
    op.create_index(op.f("ix_payments_payment_type"), "payments", ["payment_type"], unique=False)

    op.add_column("payments", sa.Column("payment_reference", sa.String(length=30), nullable=True))
    op.create_index(op.f("ix_payments_payment_reference"), "payments", ["payment_reference"], unique=True)

    op.add_column("payments", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("payments", "order_id", existing_type=sa.INTEGER(), nullable=True)

    op.create_table(
        "membership_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", "period_start"),
    )
    op.create_index(
        op.f("ix_membership_periods_membership_id"), "membership_periods", ["membership_id"], unique=False
    )

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("membership_period_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["membership_period_id"], ["membership_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_allocations_payment_id"), "payment_allocations", ["payment_id"], unique=False
    )
    op.create_index(
        op.f("ix_payment_allocations_membership_period_id"),
        "payment_allocations",
        ["membership_period_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_payment_allocations_membership_period_id"), table_name="payment_allocations")
    op.drop_index(op.f("ix_payment_allocations_payment_id"), table_name="payment_allocations")
    op.drop_table("payment_allocations")

    op.drop_index(op.f("ix_membership_periods_membership_id"), table_name="membership_periods")
    op.drop_table("membership_periods")

    # Reverting order_id to NOT NULL is safe only because, by the time anyone downgrades, no
    # membership payment (which always has a null order_id) is expected to have been created
    # yet in a state that matters — this feature is brand new as of this migration.
    op.alter_column("payments", "order_id", existing_type=sa.INTEGER(), nullable=False)

    op.drop_column("payments", "paid_at")

    op.drop_index(op.f("ix_payments_payment_reference"), table_name="payments")
    op.drop_column("payments", "payment_reference")

    op.drop_index(op.f("ix_payments_payment_type"), table_name="payments")
    op.drop_column("payments", "payment_type")
