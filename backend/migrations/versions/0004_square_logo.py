"""a square can have a logo (public URL)

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "logo_url" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        op.add_column("squares", sa.Column("logo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "logo_url")
