"""the kind of group a square is, for its starter set (W14-R10)

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "group_type" not in have:
        op.add_column("squares", sa.Column("group_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "group_type")
