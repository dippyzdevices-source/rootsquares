"""add allowed_ticket_type_ids to coupons

Revision ID: ffefbc1e1c25
Revises: 74e35aa950f5
Create Date: 2026-09-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ffefbc1e1c25'
down_revision = '74e35aa950f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('coupons', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('allowed_ticket_type_ids', sa.String(length=500), nullable=False, server_default='')
        )
    # Drop the server_default now that every existing row is backfilled — new rows set it
    # explicitly going forward via the model's own Python-side default.
    with op.batch_alter_table('coupons', schema=None) as batch_op:
        batch_op.alter_column('allowed_ticket_type_ids', server_default=None)


def downgrade():
    with op.batch_alter_table('coupons', schema=None) as batch_op:
        batch_op.drop_column('allowed_ticket_type_ids')
