"""prices as data, billing orders, paid_until on a square

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "paid_until" not in {c["name"] for c in inspector.get_columns("squares")}:
        op.add_column("squares", sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True))
    tables = set(inspector.get_table_names())
    if "plan_prices" not in tables:
        op.create_table(
            "plan_prices",
            sa.Column("key", sa.String(40), primary_key=True),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("interval", sa.String(10), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if "billing_orders" not in tables:
        op.create_table(
            "billing_orders",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("square_id", sa.Uuid(), sa.ForeignKey("squares.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("launch_package", sa.String(20), nullable=True),
            sa.Column("running_plan", sa.String(20), nullable=True),
            sa.Column("interval", sa.String(10), nullable=True),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("provider_ref", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("billing_orders")
    op.drop_table("plan_prices")
    op.drop_column("squares", "paid_until")
