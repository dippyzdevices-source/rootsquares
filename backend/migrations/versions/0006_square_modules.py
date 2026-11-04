"""a square has a list of optional modules (null = every module)

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "modules" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        op.add_column("squares", sa.Column("modules", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "modules")
