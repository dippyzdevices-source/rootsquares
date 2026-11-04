"""add heritage_image_url to site_settings

Revision ID: e6a2c4b8d013
Revises: d5f1b3a7c942
Create Date: 2026-09-29 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6a2c4b8d013'
down_revision = 'd5f1b3a7c942'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('heritage_image_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('site_settings', 'heritage_image_url')
