"""drop users.is_platform_admin: staff are the only admins (ADR 083 stage 6, W20-R6)

Revision ID: 0031
Revises: 0030

0029 copied every flagged account that had a password into `staff_users` and named the others in its log. Nothing reads the flag any more.
Downgrade brings the column back empty (no one is an admin again; staff accounts stay).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "is_platform_admin" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("is_platform_admin")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
