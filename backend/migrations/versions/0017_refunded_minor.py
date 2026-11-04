"""how much of a payment was refunded so far, for partial refunds (W13-R31)

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("billing_orders")}
    if "refunded_minor" not in have:
        op.add_column("billing_orders", sa.Column("refunded_minor", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("billing_orders", "refunded_minor")
