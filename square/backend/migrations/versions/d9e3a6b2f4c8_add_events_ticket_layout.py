"""add events.ticket_layout (how a multi-day event's tickets are shown: sections or tabs)

Revision ID: d9e3a6b2f4c8
Revises: c8d2f5a1e7b3
Create Date: 2026-10-12 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9e3a6b2f4c8'
down_revision = 'c8d2f5a1e7b3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('ticket_layout', sa.String(length=10), nullable=False, server_default='sections'))


def downgrade():
    op.drop_column('events', 'ticket_layout')
