"""add newsletter_subscribers

Revision ID: a7c1e4f9b2d6
Revises: f6b0d3e8a5c7
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa


revision = "a7c1e4f9b2d6"
down_revision = "f6b0d3e8a5c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "newsletter_subscribers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_newsletter_subscribers_email", "newsletter_subscribers", ["email"], unique=True)


def downgrade():
    op.drop_index("ix_newsletter_subscribers_email", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")
