"""squares.pending_running_plan: a downgrade from Live to Keep that starts at the next renewal (W18-R34)

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "pending_running_plan" not in have:
        with op.batch_alter_table("squares") as b:
            b.add_column(sa.Column("pending_running_plan", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as b:
        b.drop_column("pending_running_plan")
