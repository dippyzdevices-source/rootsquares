"""add order cancellation tracking fields

Revision ID: f73fb9ddb2b8
Revises: 8fd98db7a5ce
Create Date: 2026-09-28 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f73fb9ddb2b8'
down_revision = '8fd98db7a5ce'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancelled_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        batch_op.create_foreign_key(None, 'users', ['cancelled_by_user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('cancellation_reason')
        batch_op.drop_column('cancelled_at')
        batch_op.drop_column('cancelled_by_user_id')
