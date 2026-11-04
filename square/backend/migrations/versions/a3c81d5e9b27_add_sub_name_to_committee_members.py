"""add sub_name to committee_members

Revision ID: a3c81d5e9b27
Revises: 8fa03ecbaf8e
Create Date: 2026-09-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c81d5e9b27'
down_revision = '8fa03ecbaf8e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('committee_members', sa.Column('sub_name', sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column('committee_members', 'sub_name')
