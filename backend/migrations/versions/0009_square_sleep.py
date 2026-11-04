"""true sleep: the state of a sleeping square and the copy of its public contact details

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "sleep_state" not in have:
        op.add_column("squares", sa.Column("sleep_state", sa.String(10), nullable=False, server_default="awake"))
    if "sleep_contact" not in have:
        op.add_column("squares", sa.Column("sleep_contact", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "sleep_contact")
    op.drop_column("squares", "sleep_state")
