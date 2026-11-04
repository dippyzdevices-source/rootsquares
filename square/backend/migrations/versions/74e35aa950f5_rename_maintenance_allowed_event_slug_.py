"""rename maintenance_allowed_event_slug to maintenance_allowed_event_slugs, widen it

Revision ID: 74e35aa950f5
Revises: d6034c900c78
Create Date: 2026-09-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74e35aa950f5'
down_revision = 'd6034c900c78'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.alter_column(
            'maintenance_allowed_event_slug', new_column_name='maintenance_allowed_event_slugs',
            existing_type=sa.String(length=255), type_=sa.String(length=1000), existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.alter_column(
            'maintenance_allowed_event_slugs', new_column_name='maintenance_allowed_event_slug',
            existing_type=sa.String(length=1000), type_=sa.String(length=255), existing_nullable=False,
        )
