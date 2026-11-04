"""add events.sales_close_at (close ticket sales before the event, event stays live)

Revision ID: f3b5d8e1a4c7
Revises: e2a4c7d0b3f6
Create Date: 2026-10-09 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b5d8e1a4c7'
down_revision = 'e2a4c7d0b3f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('sales_close_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('events', 'sales_close_at')
