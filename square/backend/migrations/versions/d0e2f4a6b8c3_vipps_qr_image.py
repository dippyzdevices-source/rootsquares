"""vipps qr: the picture of the square's own Vipps QR code (rootsquares W16-R8)

Revision ID: d0e2f4a6b8c3
Revises: c9d1e3f5a7b2
Create Date: 2026-10-19 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0e2f4a6b8c3'
down_revision = 'c9d1e3f5a7b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site_settings') as batch:
        batch.add_column(sa.Column('vipps_qr_image_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('site_settings') as batch:
        batch.drop_column('vipps_qr_image_url')
