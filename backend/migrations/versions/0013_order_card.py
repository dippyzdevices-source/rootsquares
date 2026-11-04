"""the card brand and last four digits of a paid order, for the payment history (W12-R8)

Revision ID: 0013
Revises: 0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("billing_orders")}
    if "card_brand" not in have:
        op.add_column("billing_orders", sa.Column("card_brand", sa.String(20), nullable=True))
    if "card_last4" not in have:
        op.add_column("billing_orders", sa.Column("card_last4", sa.String(4), nullable=True))


def downgrade() -> None:
    op.drop_column("billing_orders", "card_last4")
    op.drop_column("billing_orders", "card_brand")
