"""each square has a currency (default NOK)

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A database made by the old `init-db` from the current models already has the column (and is adopted at 0001): only add it when missing.
    if "currency" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        op.add_column("squares", sa.Column("currency", sa.String(length=3), server_default="NOK", nullable=False))


def downgrade() -> None:
    op.drop_column("squares", "currency")
