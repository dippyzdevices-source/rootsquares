"""add membership_types table and seed rows

Revision ID: 772d6e31a8fc
Revises: d6213b6ccb7f
Create Date: 2026-09-10 09:50:52.924604

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '772d6e31a8fc'
down_revision = 'd6213b6ccb7f'
branch_labels = None
depends_on = None

FK_NAME = 'fk_memberships_membership_type_membership_types'


def upgrade():
    op.create_table(
        'membership_types',
        sa.Column('name', sa.String(length=20), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('name'),
    )

    membership_types = sa.table(
        'membership_types',
        sa.column('name', sa.String),
        sa.column('price', sa.Integer),
        sa.column('is_active', sa.Boolean),
        sa.column('sort_order', sa.Integer),
    )
    memberships = sa.table('memberships', sa.column('membership_type', sa.String))

    # Seed the 5 conventional types this project has always validated against, plus any other
    # value already sitting on a live Membership row — defensive, so the new foreign key below
    # can never fail against data this migration didn't anticipate.
    bind = op.get_bind()
    conventional = ['individual', 'family', 'student', 'senior', 'lifetime']
    existing = {
        row[0] for row in bind.execute(sa.select(memberships.c.membership_type).distinct())
        if row[0] is not None
    }
    names = list(dict.fromkeys(conventional + sorted(existing - set(conventional))))
    op.bulk_insert(
        membership_types,
        [
            {'name': name, 'price': 0, 'is_active': True, 'sort_order': index}
            for index, name in enumerate(names)
        ],
    )

    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.create_foreign_key(FK_NAME, 'membership_types', ['membership_type'], ['name'])


def downgrade():
    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_='foreignkey')

    op.drop_table('membership_types')
