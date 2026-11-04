"""add event_series and events.series_id (recurring events, W14-R11)

Revision ID: c6e8a0b2d4f7
Revises: b5d7f9a1c3e6
Create Date: 2026-10-14 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6e8a0b2d4f7'
down_revision = 'b5d7f9a1c3e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_series',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('frequency', sa.String(length=20), nullable=False),
        sa.Column('interval_weeks', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('nth', sa.Integer(), nullable=True),
        sa.Column('until_date', sa.Date(), nullable=True),
        sa.Column('max_count', sa.Integer(), nullable=True),
        sa.Column('horizon_days', sa.Integer(), nullable=False, server_default='120'),
        sa.Column('ended', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table('events') as batch:
        batch.add_column(sa.Column('series_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_events_series_id', 'event_series', ['series_id'], ['id'], ondelete='SET NULL')
        batch.create_index('ix_events_series_id', ['series_id'])


def downgrade():
    with op.batch_alter_table('events') as batch:
        batch.drop_index('ix_events_series_id')
        batch.drop_constraint('fk_events_series_id', type_='foreignkey')
        batch.drop_column('series_id')
    op.drop_table('event_series')
