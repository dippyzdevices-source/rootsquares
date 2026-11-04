"""add events.sales_open_at (ticket sales start, event stays live)

Revision ID: a4c6e9f2b5d8
Revises: f3b5d8e1a4c7
Create Date: 2026-10-09 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c6e9f2b5d8'
down_revision = 'f3b5d8e1a4c7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('sales_open_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('events', 'sales_open_at')
