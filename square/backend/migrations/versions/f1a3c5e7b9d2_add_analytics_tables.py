"""add the analytics tables: daily totals, pages, sources and today's visitors (ADR 090, W23-R76)

Revision ID: f1a3c5e7b9d2
Revises: e2a4c6e8b0d4
Create Date: 2026-10-27 12:00:00.000000

Aggregates only. No column of these tables holds an address, a browser string, a name or a person's id; `analytics_seen` holds one hash per visitor for the current
day only (a key that changes every day makes it, and the application empties every earlier day).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a3c5e7b9d2'
down_revision = 'e2a4c6e8b0d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'analytics_daily',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('visits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('visitors', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('day'),
    )
    op.create_table(
        'analytics_pages',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('path', sa.String(length=200), nullable=False),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('day', 'path'),
    )
    op.create_table(
        'analytics_sources',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('visits', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('day', 'source'),
    )
    op.create_table(
        'analytics_seen',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('visitor', sa.String(length=64), nullable=False),
        sa.Column('hits', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('day', 'visitor'),
    )


def downgrade():
    op.drop_table('analytics_seen')
    op.drop_table('analytics_sources')
    op.drop_table('analytics_pages')
    op.drop_table('analytics_daily')
