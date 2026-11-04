"""add committee member contact fields, replace description with quote

Revision ID: b53a6a0a6ddf
Revises: abdf26d31ef2
Create Date: 2026-09-22 21:50:44.262664

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b53a6a0a6ddf'
down_revision = 'abdf26d31ef2'
branch_labels = None
depends_on = None


def upgrade():
    # `quote` replaces `description` (a bio) in meaning, not just name — hand-adjusted from
    # autogenerate's drop+add to a rename so any existing biography text survives as the
    # member's initial quote instead of being silently dropped.
    with op.batch_alter_table('committee_members', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('member_since', sa.Integer(), nullable=True))
        batch_op.alter_column('description', new_column_name='quote', existing_type=sa.Text(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table('committee_members', schema=None) as batch_op:
        batch_op.alter_column('quote', new_column_name='description', existing_type=sa.Text(), existing_nullable=True)
        batch_op.drop_column('member_since')
        batch_op.drop_column('phone')
        batch_op.drop_column('email')
