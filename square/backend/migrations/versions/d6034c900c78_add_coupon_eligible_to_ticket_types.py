"""add coupon_eligible to ticket_types

Revision ID: d6034c900c78
Revises: 16596fbc6f94
Create Date: 2026-09-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6034c900c78'
down_revision = '16596fbc6f94'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('coupon_eligible', sa.Boolean(), nullable=False, server_default=sa.true())
        )
    # Drop the server_default now that every existing row is backfilled — new rows set it
    # explicitly going forward via the model's own Python-side default.
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.alter_column('coupon_eligible', server_default=None)


def downgrade():
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.drop_column('coupon_eligible')
