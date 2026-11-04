"""a square has a launch package and a running plan

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "launch_package" not in have:
        op.add_column("squares", sa.Column("launch_package", sa.String(20), nullable=True))
    if "running_plan" not in have:
        op.add_column("squares", sa.Column("running_plan", sa.String(20), nullable=False, server_default="live"))


def downgrade() -> None:
    op.drop_column("squares", "running_plan")
    op.drop_column("squares", "launch_package")
