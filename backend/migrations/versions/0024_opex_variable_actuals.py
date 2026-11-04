"""opex phase 3: variable cost lines and actual amounts per month (W16-R9)

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    have = {c["name"] for c in insp.get_columns("opex_items")}
    with op.batch_alter_table("opex_items") as b:
        if "cost_type" not in have:
            b.add_column(sa.Column("cost_type", sa.String(length=10), nullable=False, server_default="fixed"))
        if "variable_bp" not in have:
            b.add_column(sa.Column("variable_bp", sa.Integer(), nullable=False, server_default="0"))
        if "variable_fixed_minor" not in have:
            b.add_column(sa.Column("variable_fixed_minor", sa.Integer(), nullable=False, server_default="0"))
    if "opex_actuals" not in insp.get_table_names():
        op.create_table(
            "opex_actuals",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("item_id", sa.Uuid(), sa.ForeignKey("opex_items.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("month", sa.String(length=7), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("item_id", "month", name="uq_opex_actual"),
        )


def downgrade() -> None:
    op.drop_table("opex_actuals")
    with op.batch_alter_table("opex_items") as b:
        b.drop_column("variable_fixed_minor")
        b.drop_column("variable_bp")
        b.drop_column("cost_type")
