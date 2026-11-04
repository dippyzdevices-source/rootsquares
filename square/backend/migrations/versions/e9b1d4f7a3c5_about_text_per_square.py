"""each square has its own About page text

rootsquares change (W6-R58): bca-oslo's history text was removed (W6-R41); a square now writes its own About text as a setting.

Revision ID: e9b1d4f7a3c5
Revises: d8a0c3e6f2b4
"""
from alembic import op
import sqlalchemy as sa

revision = 'e9b1d4f7a3c5'
down_revision = 'd8a0c3e6f2b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('about_text', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'about_text')
