"""add payments.surcharge_amount

Revision ID: e2b5c8d3f6a1
Revises: d1a4b7c2e5f9
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa


revision = "e2b5c8d3f6a1"
down_revision = "d1a4b7c2e5f9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("surcharge_amount", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("payments", "surcharge_amount")
