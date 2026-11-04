"""add event sub_name

Revision ID: c3e7a9b5d2f4
Revises: b2d6f8a4c1e3
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


revision = "c3e7a9b5d2f4"
down_revision = "b2d6f8a4c1e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("sub_name", sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column("events", "sub_name")
