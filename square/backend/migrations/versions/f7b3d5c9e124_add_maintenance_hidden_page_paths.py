"""add maintenance_hidden_page_paths to site_settings

Revision ID: f7b3d5c9e124
Revises: e6a2c4b8d013
Create Date: 2026-09-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7b3d5c9e124'
down_revision = 'e6a2c4b8d013'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'maintenance_hidden_page_paths',
                sa.String(length=500),
                nullable=False,
                server_default='',
            )
        )


def downgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.drop_column('maintenance_hidden_page_paths')
