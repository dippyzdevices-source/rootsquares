"""add newsletter_issues.scheduled_for

Revision ID: d7a0b3c6e9f2
Revises: c6f9a2b5d8e1
Create Date: 2026-10-06

"""
from alembic import op
import sqlalchemy as sa


revision = "d7a0b3c6e9f2"
down_revision = "c6f9a2b5d8e1"
branch_labels = None
depends_on = None


def upgrade():
    # Null for every existing issue (they were all send-now). status "scheduled" needs no schema
    # change — `status` is a plain string.
    op.add_column(
        "newsletter_issues",
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("newsletter_issues", "scheduled_for")
