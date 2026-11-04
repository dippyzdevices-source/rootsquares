"""payment fees: per-method convenience/processing fee settings + payments.processing_fee_amount

Revision ID: e4b7c1d9a2f6
Revises: d9e3a6b2f4c8
Create Date: 2026-10-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4b7c1d9a2f6'
down_revision = 'c7e9a1b3d5f8'  # rootsquares: chained onto the square's own head (port of bca-oslo ffa0802)
branch_labels = None
depends_on = None

# (method, convenience %, processing %, processing fixed øre) — defaults keep today's behaviour.
METHODS = (("vipps_qr", "0", "0", "0"), ("vipps_app", "5", "2.99", "100"), ("cash", "0", "0", "0"))


def upgrade():
    for method, conv, proc, fixed in METHODS:
        op.add_column('site_settings', sa.Column(f'{method}_convenience_percent', sa.Numeric(5, 2), nullable=False, server_default=conv))
        op.add_column('site_settings', sa.Column(f'{method}_processing_percent', sa.Numeric(5, 2), nullable=False, server_default=proc))
        op.add_column('site_settings', sa.Column(f'{method}_processing_fixed_ore', sa.Integer(), nullable=False, server_default=fixed))
    op.add_column('payments', sa.Column('processing_fee_amount', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('payments', 'processing_fee_amount')
    for method, *_ in METHODS:
        op.drop_column('site_settings', f'{method}_processing_fixed_ore')
        op.drop_column('site_settings', f'{method}_processing_percent')
        op.drop_column('site_settings', f'{method}_convenience_percent')
