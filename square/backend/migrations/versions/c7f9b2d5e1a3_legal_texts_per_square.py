"""each square has its own privacy policy and terms of sale text

rootsquares change (W6-R51): bca-oslo's legal texts were removed (W6-R41); a square now writes its own, as plain text in site_settings.

Revision ID: c7f9b2d5e1a3
Revises: b6e8a1c4d7f0
"""
from alembic import op
import sqlalchemy as sa

revision = 'c7f9b2d5e1a3'
down_revision = 'b6e8a1c4d7f0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('privacy_text', sa.Text(), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('terms_text', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'terms_text')
    op.drop_column('site_settings', 'privacy_text')
