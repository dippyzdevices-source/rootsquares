"""the voucher code a square was created with (W14-R30)

Revision ID: 0021
Revises: 0020
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "voucher_code" not in have:
        op.add_column("squares", sa.Column("voucher_code", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "voucher_code")
