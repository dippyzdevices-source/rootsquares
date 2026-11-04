"""squares.custom_modules, custom_amount_minor, custom_interval: the custom package a platform admin agrees with one square (W19-R20)

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    with op.batch_alter_table("squares") as b:
        if "custom_modules" not in have:
            b.add_column(sa.Column("custom_modules", sa.Text(), nullable=True))
        if "custom_amount_minor" not in have:
            b.add_column(sa.Column("custom_amount_minor", sa.Integer(), nullable=True))
        if "custom_interval" not in have:
            b.add_column(sa.Column("custom_interval", sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as b:
        b.drop_column("custom_interval")
        b.drop_column("custom_amount_minor")
        b.drop_column("custom_modules")
