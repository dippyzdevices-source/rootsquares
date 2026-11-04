"""each square has its own time zone (default Europe/Oslo, as bca-oslo had)

rootsquares change (W6-R54): the refund cut-off ("not after the event day") used Europe/Oslo for every square.

Revision ID: d8a0c3e6f2b4
Revises: c7f9b2d5e1a3
"""
from alembic import op
import sqlalchemy as sa

revision = 'd8a0c3e6f2b4'
down_revision = 'c7f9b2d5e1a3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Europe/Oslo'))


def downgrade():
    op.drop_column('site_settings', 'timezone')
