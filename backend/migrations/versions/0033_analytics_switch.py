"""squares.analytics_enabled: the owner's switch for counting the visits of the square's site (ADR 090, W23-R77)

Revision ID: 0033
Revises: 0032

One column, off for every square. The platform stores no number about a square's visits: only this switch. Downgrade drops the column (counting stops).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "analytics_enabled" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        return
    with op.batch_alter_table("squares") as batch:
        batch.add_column(sa.Column("analytics_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("squares") as batch:
        batch.drop_column("analytics_enabled")
