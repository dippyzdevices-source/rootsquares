"""when a square fell asleep and when it was archived (W13-R48)

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "asleep_since" not in have:
        op.add_column("squares", sa.Column("asleep_since", sa.DateTime(timezone=True), nullable=True))
        # squares that already sleep start their 12 months today (nobody is archived because of an unknown date)
        op.execute("UPDATE squares SET asleep_since = CURRENT_TIMESTAMP WHERE sleep_state = 'sleeping'")
    if "archived_at" not in have:
        op.add_column("squares", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "archived_at")
    op.drop_column("squares", "asleep_since")
