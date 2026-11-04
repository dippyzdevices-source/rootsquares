"""squares: the owner's call for IT help with the own website domain (ADR 098, W26-R10)

Revision ID: 0038
Revises: 0037

One nullable column, empty for every square: `site_domain_help_at` (when the owner asked staff for IT help; a small one-time support fee applies).
Downgrade drops the column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    if "site_domain_help_at" not in have:
        with op.batch_alter_table("squares") as batch:
            batch.add_column(sa.Column("site_domain_help_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as batch:
        batch.drop_column("site_domain_help_at")
