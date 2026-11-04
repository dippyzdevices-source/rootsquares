"""add site_settings.vipps_app_public

Revision ID: f3c6d9a4b7e2
Revises: e2b5c8d3f6a1
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa


revision = "f3c6d9a4b7e2"
down_revision = "e2b5c8d3f6a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "site_settings",
        sa.Column("vipps_app_public", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("site_settings", "vipps_app_public")
