"""add general_income: income typed in by hand in the general book (W15-R16)

Revision ID: b6d8f0a2c4e7
Revises: a4c6e8b0d2f5
Create Date: 2026-10-15 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6d8f0a2c4e7'
down_revision = 'a4c6e8b0d2f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'general_income',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('general_income')
