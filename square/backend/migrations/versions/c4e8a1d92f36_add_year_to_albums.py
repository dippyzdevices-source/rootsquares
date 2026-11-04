"""add year to albums

Revision ID: c4e8a1d92f36
Revises: b7d24f6a1c80
Create Date: 2026-09-29 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e8a1d92f36'
down_revision = 'b7d24f6a1c80'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('albums', sa.Column('year', sa.Integer(), nullable=True))
    # Best-effort backfill for any existing album (the gallery is empty in production today).
    op.execute("UPDATE albums SET year = EXTRACT(YEAR FROM created_at)::int")
    op.alter_column('albums', 'year', nullable=False)
    op.create_index('ix_albums_year', 'albums', ['year'])


def downgrade():
    op.drop_index('ix_albums_year', table_name='albums')
    op.drop_column('albums', 'year')
