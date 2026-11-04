"""the Stripe subscription of a square and whether its renewal was cancelled (W12-R13)

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "stripe_subscription_id" not in have:
        op.add_column("squares", sa.Column("stripe_subscription_id", sa.String(60), nullable=True))
    if "renewal_cancelled" not in have:
        op.add_column("squares", sa.Column("renewal_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("squares", "renewal_cancelled")
    op.drop_column("squares", "stripe_subscription_id")
