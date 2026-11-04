"""add event_series.first_date so "N times" counts from the first occurrence even after it is deleted (W15-R5)

Revision ID: f3b5d7a9c1e4
Revises: e9b1d3f5a7c2
Create Date: 2026-10-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b5d7a9c1e4'
down_revision = 'e9b1d3f5a7c2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event_series', sa.Column('first_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('event_series', 'first_date')
