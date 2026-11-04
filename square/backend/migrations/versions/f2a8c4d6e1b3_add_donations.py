"""add donations, payments.donation_id and the donation settings (W14-R4)

Revision ID: f2a8c4d6e1b3
Revises: e1f4a7c3b9d2
Create Date: 2026-10-14 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a8c4d6e1b3'
down_revision = 'e1f4a7c3b9d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'donations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reference', sa.String(length=30), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('donor_name', sa.String(length=200), nullable=False),
        sa.Column('donor_email', sa.String(length=255), nullable=False),
        sa.Column('anonymous', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_donations_reference', 'donations', ['reference'], unique=True)
    op.create_index('ix_donations_user_id', 'donations', ['user_id'])
    op.create_index('ix_donations_donor_email', 'donations', ['donor_email'])
    op.create_index('ix_donations_status', 'donations', ['status'])
    op.add_column('payments', sa.Column('donation_id', sa.Integer(), sa.ForeignKey('donations.id'), nullable=True))
    op.create_index('ix_payments_donation_id', 'payments', ['donation_id'])
    op.add_column('site_settings', sa.Column('donation_amounts', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('donation_intro', sa.Text(), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('donation_thanks', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'donation_thanks')
    op.drop_column('site_settings', 'donation_intro')
    op.drop_column('site_settings', 'donation_amounts')
    op.drop_index('ix_payments_donation_id', table_name='payments')
    op.drop_column('payments', 'donation_id')
    op.drop_table('donations')
