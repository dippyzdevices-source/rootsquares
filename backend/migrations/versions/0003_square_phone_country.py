"""each square has a phone country (default NO)

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "phone_country" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        op.add_column("squares", sa.Column("phone_country", sa.String(length=2), server_default="NO", nullable=False))


def downgrade() -> None:
    op.drop_column("squares", "phone_country")
