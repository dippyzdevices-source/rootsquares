"""stripe: the admin switch and the fee settings for card payments through Stripe (rootsquares W16-R6)

Revision ID: c9d1e3f5a7b2
Revises: b8c0d2e4f6a1
Create Date: 2026-10-19 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d1e3f5a7b2'
down_revision = 'b8c0d2e4f6a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site_settings') as batch:
        batch.add_column(sa.Column('stripe_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('stripe_convenience_percent', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch.add_column(sa.Column('stripe_processing_percent', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch.add_column(sa.Column('stripe_processing_fixed_ore', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('site_settings') as batch:
        batch.drop_column('stripe_processing_fixed_ore')
        batch.drop_column('stripe_processing_percent')
        batch.drop_column('stripe_convenience_percent')
        batch.drop_column('stripe_enabled')
