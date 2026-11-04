"""add general_income_target: a yearly income target per income source in the general book (W17-R6)

Revision ID: e2a4c6e8b0d4
Revises: d0e2f4a6b8c3
Create Date: 2026-10-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2a4c6e8b0d4'
down_revision = 'd0e2f4a6b8c3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'general_income_target',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'source', name='uq_general_income_target_year_source'),
    )


def downgrade():
    op.drop_table('general_income_target')
