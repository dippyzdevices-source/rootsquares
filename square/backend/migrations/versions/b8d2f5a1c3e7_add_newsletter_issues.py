"""add newsletter_issues

Revision ID: b8d2f5a1c3e7
Revises: a7c1e4f9b2d6
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa


revision = "b8d2f5a1c3e7"
down_revision = "a7c1e4f9b2d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "newsletter_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recipients_total", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("last_subscriber_id", sa.Integer(), nullable=False),
        sa.Column("sent_by_user_id", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("newsletter_issues")
