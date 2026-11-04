"""expenses.event_id may be empty: the general book of Accounting without Events (W14-R15)

Revision ID: d8a0c2e4f6b1
Revises: c6e8a0b2d4f7
Create Date: 2026-10-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8a0c2e4f6b1'
down_revision = 'c6e8a0b2d4f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.alter_column('event_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    # an expense with no event cannot exist in the old schema
    op.execute('DELETE FROM expenses WHERE event_id IS NULL')
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.alter_column('event_id', existing_type=sa.Integer(), nullable=False)
