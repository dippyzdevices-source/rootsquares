"""add newsletter_issues.extra_recipients and extras_sent

Revision ID: c9e3a6b2d4f8
Revises: b8d2f5a1c3e7
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa


revision = "c9e3a6b2d4f8"
down_revision = "b8d2f5a1c3e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("newsletter_issues", sa.Column("extra_recipients", sa.Text(), nullable=False, server_default=""))
    op.add_column("newsletter_issues", sa.Column("extras_sent", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("newsletter_issues", "extras_sent")
    op.drop_column("newsletter_issues", "extra_recipients")
