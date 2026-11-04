"""add sponsors

Revision ID: a1c9e5d7b3f2
Revises: f7b3d5c9e124
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


revision = "a1c9e5d7b3f2"
down_revision = "f7b3d5c9e124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sponsors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("logo_url", sa.String(length=500)),
        sa.Column("website_url", sa.String(length=500)),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sponsors_is_active", "sponsors", ["is_active"])


def downgrade():
    op.drop_index("ix_sponsors_is_active", table_name="sponsors")
    op.drop_table("sponsors")
