"""add coupons table, ticket_types.age_category, orders coupon fields

Revision ID: 16596fbc6f94
Revises: eb75e962841f
Create Date: 2026-09-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16596fbc6f94'
down_revision = 'eb75e962841f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'coupons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('discount_percent', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'code', name='uq_coupons_event_code'),
    )
    with op.batch_alter_table('coupons', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_coupons_event_id'), ['event_id'], unique=False)

    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('age_category', sa.String(length=20), nullable=False, server_default='other')
        )
    # Drop the server_default now that every existing row is backfilled — new rows set it
    # explicitly going forward via the model's own Python-side default.
    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.alter_column('age_category', server_default=None)

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('coupon_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('coupon_code', sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column('discount_amount', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.create_foreign_key('fk_orders_coupon_id_coupons', 'coupons', ['coupon_id'], ['id'])
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('discount_amount', server_default=None)


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_coupon_id_coupons', type_='foreignkey')
        batch_op.drop_column('discount_amount')
        batch_op.drop_column('coupon_code')
        batch_op.drop_column('coupon_id')

    with op.batch_alter_table('ticket_types', schema=None) as batch_op:
        batch_op.drop_column('age_category')

    with op.batch_alter_table('coupons', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_coupons_event_id'))

    op.drop_table('coupons')
