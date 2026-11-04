"""add ticket_types.valid_on (the day a ticket is for, used to section tickets by date)

Revision ID: c8d2f5a1e7b3
Revises: a4c6e9f2b5d8
Create Date: 2026-10-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8d2f5a1e7b3'
down_revision = 'f1c2e5a8b7d9'  # bca-oslo chains onto a4c6e9f2b5d8; the square's own head is f1c2e5a8b7d9 (W13-R52)
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ticket_types', sa.Column('valid_on', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('ticket_types', 'valid_on')
