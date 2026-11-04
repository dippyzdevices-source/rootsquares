"""add billing_frequency and contact_for_price to membership_types

Revision ID: 9a9b8b138aa1
Revises: 772d6e31a8fc
Create Date: 2026-09-10 11:09:18.176516

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a9b8b138aa1'
down_revision = '772d6e31a8fc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('membership_types', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'billing_frequency', sa.String(length=20), nullable=False,
                server_default='yearly',
            )
        )
        batch_op.add_column(
            sa.Column(
                'contact_for_price', sa.Boolean(), nullable=False,
                server_default=sa.false(),
            )
        )

    # Lifetime is a one-time, often individually-negotiated fee — point members at Contact
    # instead of a stale 0 kr price, matching the concrete case that prompted this feature.
    # Any type can be switched the same way from the admin UI; this is just the seeded default.
    membership_types = sa.table(
        'membership_types', sa.column('name', sa.String), sa.column('contact_for_price', sa.Boolean)
    )
    op.execute(
        membership_types.update()
        .where(membership_types.c.name == 'lifetime')
        .values(contact_for_price=True)
    )

    with op.batch_alter_table('membership_types', schema=None) as batch_op:
        batch_op.alter_column('billing_frequency', server_default=None)
        batch_op.alter_column('contact_for_price', server_default=None)


def downgrade():
    with op.batch_alter_table('membership_types', schema=None) as batch_op:
        batch_op.drop_column('contact_for_price')
        batch_op.drop_column('billing_frequency')
