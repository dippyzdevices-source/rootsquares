"""prospects: people who asked to speak to us about a custom package (W19-R22)

Revision ID: 0028
Revises: 0027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "prospects" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "prospects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False, index=True),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="pricing_custom"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="new", index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("prospects")
