"""newsletter_issues.moved_to_message_id: an old issue copied into Messages (newsletter fold-in step 2, W14-R18)

Revision ID: e9b1d3f5a7c2
Revises: d8a0c2e4f6b1
Create Date: 2026-10-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9b1d3f5a7c2'
down_revision = 'd8a0c2e4f6b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('newsletter_issues') as batch_op:
        batch_op.add_column(sa.Column('moved_to_message_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('newsletter_issues') as batch_op:
        batch_op.drop_column('moved_to_message_id')
