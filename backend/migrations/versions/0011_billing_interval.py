"""a square has the owner's default billing period (month or year)

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "billing_interval" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        op.add_column("squares", sa.Column("billing_interval", sa.String(5), nullable=False, server_default="month"))


def downgrade() -> None:
    op.drop_column("squares", "billing_interval")
