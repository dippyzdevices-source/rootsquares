"""payment_credentials: each square's own payment provider keys, encrypted (rootsquares W16-R4)

Revision ID: b8c0d2e4f6a1
Revises: a7b9d1e3c5f2
Create Date: 2026-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c0d2e4f6a1'
down_revision = 'a7b9d1e3c5f2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payment_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('mode', sa.String(length=12), nullable=False, server_default='test'),
        sa.Column('hint', sa.JSON(), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('webhook_registered', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', name='uq_payment_credentials_provider'),
    )


def downgrade():
    op.drop_table('payment_credentials')
