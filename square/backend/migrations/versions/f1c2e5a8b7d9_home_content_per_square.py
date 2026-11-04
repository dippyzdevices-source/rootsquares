"""each square has its own home page, header and footer words

rootsquares change (W6-R64): bca-oslo's headline, Bengali line, numbers and top-bar text were removed (W6-R36, W6-R41); a square now sets its own.

Revision ID: f1c2e5a8b7d9
Revises: e9b1d4f7a3c5
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1c2e5a8b7d9'
down_revision = 'e9b1d4f7a3c5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('home_content', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('site_settings', 'home_content')
