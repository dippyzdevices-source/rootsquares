"""add general_budget: a yearly budget per expense category in the general book (W15-R18)

Revision ID: c7e9a1b3d5f8
Revises: b6d8f0a2c4e7
Create Date: 2026-10-15 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e9a1b3d5f8'
down_revision = 'b6d8f0a2c4e7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'general_budget',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'category', name='uq_general_budget_year_category'),
    )


def downgrade():
    op.drop_table('general_budget')
