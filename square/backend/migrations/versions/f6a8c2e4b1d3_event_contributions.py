"""event_contributions: donations and sponsorships received for an event

Revision ID: f6a8c2e4b1d3
Revises: e4b7c1d9a2f6
Create Date: 2026-10-19 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a8c2e4b1d3'
down_revision = 'e4b7c1d9a2f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_contributions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='paid', nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_event_contributions_event_id'), 'event_contributions', ['event_id'])


def downgrade():
    op.drop_index(op.f('ix_event_contributions_event_id'), table_name='event_contributions')
    op.drop_table('event_contributions')
