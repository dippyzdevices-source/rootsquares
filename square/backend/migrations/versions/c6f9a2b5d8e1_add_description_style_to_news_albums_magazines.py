"""add description_style override to news, albums, magazines

Revision ID: c6f9a2b5d8e1
Revises: b5e8f1a4c7d9
Create Date: 2026-10-06

"""
from alembic import op
import sqlalchemy as sa


revision = "c6f9a2b5d8e1"
down_revision = "b5e8f1a4c7d9"
branch_labels = None
depends_on = None

TABLES = ("news", "albums", "magazines")


def upgrade():
    # Nullable = use the site-wide default, so every existing row looks exactly as before.
    for table in TABLES:
        op.add_column(table, sa.Column("description_style", sa.String(length=20), nullable=True))


def downgrade():
    for table in reversed(TABLES):
        op.drop_column(table, "description_style")
