"""stacking vouchers: platform settings, the vouchers an order used, a 'can be combined' switch (W15-R19)

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "platform_settings" not in tables:
        op.create_table(
            "platform_settings",
            sa.Column("key", sa.String(length=60), primary_key=True),
            sa.Column("value", sa.String(length=200), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if "billing_order_vouchers" not in tables:
        op.create_table(
            "billing_order_vouchers",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("order_id", sa.Uuid(), sa.ForeignKey("billing_orders.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("voucher_id", sa.Uuid(), nullable=False, index=True),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("discount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("order_id", "voucher_id", name="uq_order_voucher"),
        )
    voucher_cols = {c["name"] for c in inspector.get_columns("vouchers")}
    if "stackable" not in voucher_cols:
        op.add_column("vouchers", sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.false()))
    # several codes can be kept on a square and written on an order
    with op.batch_alter_table("squares") as b:
        b.alter_column("voucher_code", existing_type=sa.String(length=40), type_=sa.String(length=120), existing_nullable=True)
    with op.batch_alter_table("billing_orders") as b:
        b.alter_column("voucher_code", existing_type=sa.String(length=40), type_=sa.String(length=120), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("billing_orders") as b:
        b.alter_column("voucher_code", existing_type=sa.String(length=120), type_=sa.String(length=40), existing_nullable=True)
    with op.batch_alter_table("squares") as b:
        b.alter_column("voucher_code", existing_type=sa.String(length=120), type_=sa.String(length=40), existing_nullable=True)
    op.drop_column("vouchers", "stackable")
    op.drop_table("billing_order_vouchers")
    op.drop_table("platform_settings")
