"""add site_settings.message_footer_update, message_footer_service (own wording of the Messages footers, W15-R10)

Revision ID: a4c6e8b0d2f5
Revises: f3b5d7a9c1e4
Create Date: 2026-10-15 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c6e8b0d2f5'
down_revision = 'f3b5d7a9c1e4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('message_footer_update', sa.Text(), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('message_footer_service', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'message_footer_service')
    op.drop_column('site_settings', 'message_footer_update')
