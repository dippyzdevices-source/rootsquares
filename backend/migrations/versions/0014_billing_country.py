"""the owner's billing country and the Stripe customer of an organisation (W12-R12)

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("organizations")}
    if "billing_country" not in have:
        op.add_column("organizations", sa.Column("billing_country", sa.String(2), nullable=True))
    if "stripe_customer_id" not in have:
        op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "stripe_customer_id")
    op.drop_column("organizations", "billing_country")
