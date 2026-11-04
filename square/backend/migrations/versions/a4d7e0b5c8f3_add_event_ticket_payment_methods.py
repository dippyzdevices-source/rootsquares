"""add events.ticket_payment_methods

Revision ID: a4d7e0b5c8f3
Revises: f3c6d9a4b7e2
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa


revision = "a4d7e0b5c8f3"
down_revision = "f3c6d9a4b7e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "events",
        sa.Column("ticket_payment_methods", sa.String(length=10), nullable=False, server_default="both"),
    )


def downgrade():
    op.drop_column("events", "ticket_payment_methods")
