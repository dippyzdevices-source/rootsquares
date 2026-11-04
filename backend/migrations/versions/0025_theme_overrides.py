"""squares.theme_overrides: the owner's own colours and font pair (W18-R18)

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "theme_overrides" not in have:
        with op.batch_alter_table("squares") as b:
            b.add_column(sa.Column("theme_overrides", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as b:
        b.drop_column("theme_overrides")
