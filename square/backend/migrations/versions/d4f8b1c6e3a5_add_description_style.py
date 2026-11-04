"""add site_settings.description_style

Revision ID: d4f8b1c6e3a5
Revises: c3e7a9b5d2f4
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


revision = "d4f8b1c6e3a5"
down_revision = "c3e7a9b5d2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "site_settings",
        sa.Column("description_style", sa.String(length=20), nullable=False, server_default="karla"),
    )


def downgrade():
    op.drop_column("site_settings", "description_style")
