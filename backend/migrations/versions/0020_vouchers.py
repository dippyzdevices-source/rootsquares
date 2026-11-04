"""vouchers, partners and the voucher columns of billing orders (W14-R27)

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "partners" not in tables:
        op.create_table(
            "partners",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=200), nullable=True),
            sa.Column("commission_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if "vouchers" not in tables:
        op.create_table(
            "vouchers",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("kind", sa.String(length=10), nullable=False),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("applies_to", sa.String(length=12), nullable=False, server_default="all"),
            sa.Column("packages", sa.JSON(), nullable=True),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("once_per_org", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("new_customers_only", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("partner_id", sa.Uuid(), sa.ForeignKey("partners.id", ondelete="SET NULL"), nullable=True),
            sa.Column("note", sa.String(length=300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_vouchers_code", "vouchers", ["code"], unique=True)
        op.create_index("ix_vouchers_partner_id", "vouchers", ["partner_id"])
    have = {c["name"] for c in inspector.get_columns("billing_orders")}
    if "list_minor" not in have:
        op.add_column("billing_orders", sa.Column("list_minor", sa.Integer(), nullable=True))
    if "discount_minor" not in have:
        op.add_column("billing_orders", sa.Column("discount_minor", sa.Integer(), nullable=False, server_default="0"))
    if "voucher_id" not in have:
        op.add_column("billing_orders", sa.Column("voucher_id", sa.Uuid(), nullable=True))
        op.create_index("ix_billing_orders_voucher_id", "billing_orders", ["voucher_id"])
    if "voucher_code" not in have:
        op.add_column("billing_orders", sa.Column("voucher_code", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("billing_orders", "voucher_code")
    op.drop_index("ix_billing_orders_voucher_id", table_name="billing_orders")
    op.drop_column("billing_orders", "voucher_id")
    op.drop_column("billing_orders", "discount_minor")
    op.drop_column("billing_orders", "list_minor")
    op.drop_table("vouchers")
    op.drop_table("partners")
