"""add events.description_style

Revision ID: e5a9c2d7f4b6
Revises: d4f8b1c6e3a5
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


revision = "e5a9c2d7f4b6"
down_revision = "d4f8b1c6e3a5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("description_style", sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column("events", "description_style")
