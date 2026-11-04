"""add maintenance_allowed_page_paths to site_settings

Revision ID: 082d5035d12d
Revises: f73fb9ddb2b8
Create Date: 2026-09-28 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '082d5035d12d'
down_revision = 'f73fb9ddb2b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'maintenance_allowed_page_paths',
                sa.String(length=500),
                nullable=False,
                server_default='',
            )
        )


def downgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.drop_column('maintenance_allowed_page_paths')
