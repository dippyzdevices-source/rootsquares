"""add membership_type_changes

Revision ID: b7d24f6a1c80
Revises: a3c81d5e9b27
Create Date: 2026-09-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d24f6a1c80'
down_revision = 'a3c81d5e9b27'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'membership_type_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('from_type', sa.String(length=20), nullable=False),
        sa.Column('to_type', sa.String(length=20), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_membership_type_changes_membership_id', 'membership_type_changes', ['membership_id'])


def downgrade():
    op.drop_index('ix_membership_type_changes_membership_id', table_name='membership_type_changes')
    op.drop_table('membership_type_changes')
