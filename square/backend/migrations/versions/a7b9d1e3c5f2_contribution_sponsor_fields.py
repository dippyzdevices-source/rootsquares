"""event_contributions: sponsor contact fields and an optional amount (public donate / sponsor forms)

Revision ID: a7b9d1e3c5f2
Revises: f6a8c2e4b1d3
Create Date: 2026-10-19 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b9d1e3c5f2'
down_revision = 'f6a8c2e4b1d3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('event_contributions', sa.Column('contact_name', sa.String(length=200), nullable=True))
    op.add_column('event_contributions', sa.Column('phone', sa.String(length=30), nullable=True))
    op.add_column('event_contributions', sa.Column('website', sa.String(length=300), nullable=True))
    op.add_column('event_contributions', sa.Column('requirements', sa.Text(), nullable=True))
    # A sponsorship enquiry may name no amount yet; an admin sets it before marking it received.
    op.alter_column('event_contributions', 'amount', existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Enquiries without an amount cannot be kept once the column is required again.
    op.execute("DELETE FROM event_contributions WHERE amount IS NULL")
    op.alter_column('event_contributions', 'amount', existing_type=sa.Integer(), nullable=False)
    op.drop_column('event_contributions', 'requirements')
    op.drop_column('event_contributions', 'website')
    op.drop_column('event_contributions', 'phone')
    op.drop_column('event_contributions', 'contact_name')
