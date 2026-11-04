"""when a renewal payment failed and has not been put right (W12-R18)

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "payment_failed_at" not in have:
        op.add_column("squares", sa.Column("payment_failed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "payment_failed_at")
