"""add events.facebook_url / instagram_url

Revision ID: d1a4b7c2e5f9
Revises: c9e3a6b2d4f8
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa


revision = "d1a4b7c2e5f9"
down_revision = "c9e3a6b2d4f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("facebook_url", sa.String(length=500), nullable=True))
    op.add_column("events", sa.Column("instagram_url", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("events", "instagram_url")
    op.drop_column("events", "facebook_url")
