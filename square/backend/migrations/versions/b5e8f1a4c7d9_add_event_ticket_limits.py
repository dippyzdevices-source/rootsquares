"""add events ticket limits (per-email, coupon adult/child)

Revision ID: b5e8f1a4c7d9
Revises: a4d7e0b5c8f3
Create Date: 2026-10-06

"""
from alembic import op
import sqlalchemy as sa


revision = "b5e8f1a4c7d9"
down_revision = "a4d7e0b5c8f3"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable = no limit, so every existing event keeps today's behaviour (both caps were off).
    op.add_column("events", sa.Column("max_tickets_per_email", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("coupon_max_adult", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("coupon_max_child", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("events", "coupon_max_child")
    op.drop_column("events", "coupon_max_adult")
    op.drop_column("events", "max_tickets_per_email")
