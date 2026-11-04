"""each square has its own Vipps number; Vipps QR starts off

rootsquares change (W6-R38): bca-oslo hardcoded its own Vipps number and QR image, so payments of every square would have gone to BCA.
The number is now a setting (`site_settings.vipps_number`), and Vipps QR is only offered while it is switched on AND a number is set.

Revision ID: b6e8a1c4d7f0
Revises: a4c6e9f2b5d8
"""
from alembic import op
import sqlalchemy as sa

revision = 'b6e8a1c4d7f0'
down_revision = 'a4c6e9f2b5d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('vipps_number', sa.String(length=20), nullable=True))
    op.alter_column('site_settings', 'vipps_qr_enabled', existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.false())
    # No square has a number yet, so none may offer Vipps QR.
    op.execute("UPDATE site_settings SET vipps_qr_enabled = false")


def downgrade():
    op.alter_column('site_settings', 'vipps_qr_enabled', existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.true())
    op.drop_column('site_settings', 'vipps_number')
