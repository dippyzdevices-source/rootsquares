"""add members.erase_requested_at, members.erased_at, users.disabled_at (GDPR erase = anonymise, W14-R3)

Revision ID: e1f4a7c3b9d2
Revises: d9e3a6b2f4c8
Create Date: 2026-10-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f4a7c3b9d2'
down_revision = 'd9e3a6b2f4c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('erase_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('members', sa.Column('erased_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'disabled_at')
    op.drop_column('members', 'erased_at')
    op.drop_column('members', 'erase_requested_at')
