"""add the bank transfer settings (W14-R6)

Revision ID: a3c5e7b9d1f2
Revises: f2a8c4d6e1b3
Create Date: 2026-10-14 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c5e7b9d1f2'
down_revision = 'f2a8c4d6e1b3'
branch_labels = None
depends_on = None

TEXT_COLUMNS = (
    ('bank_account_holder', 200),
    ('bank_name', 200),
    ('bank_account_number', 60),
    ('bank_iban', 60),
    ('bank_bic', 30),
)


def upgrade():
    op.add_column('site_settings', sa.Column('bank_transfer_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    for name, length in TEXT_COLUMNS:
        op.add_column('site_settings', sa.Column(name, sa.String(length=length), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('bank_transfer_note', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'bank_transfer_note')
    for name, _ in reversed(TEXT_COLUMNS):
        op.drop_column('site_settings', name)
    op.drop_column('site_settings', 'bank_transfer_enabled')
