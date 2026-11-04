"""staff lockout: staff_users.failed_attempts and locked_until, staff_sessions.second_step_failures (ADR 083 stage 4, W20-R5)

Revision ID: 0030
Revises: 0029
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def _missing(table: str, name: str) -> bool:
    return name not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _missing("staff_users", "failed_attempts"):
        op.add_column("staff_users", sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"))
    if _missing("staff_users", "locked_until"):
        op.add_column("staff_users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    if _missing("staff_sessions", "second_step_failures"):
        op.add_column("staff_sessions", sa.Column("second_step_failures", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("staff_sessions", "second_step_failures")
    op.drop_column("staff_users", "locked_until")
    op.drop_column("staff_users", "failed_attempts")
