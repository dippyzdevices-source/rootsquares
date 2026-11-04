"""update site_settings placeholder phone and address to real values

Revision ID: 8fa03ecbaf8e
Revises: effbb83eff55
Create Date: 2026-09-28 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8fa03ecbaf8e'
down_revision = 'effbb83eff55'
branch_labels = None
depends_on = None

OLD_PHONE = '+47 000 00 000'
NEW_PHONE = OLD_PHONE  # rootsquares change W6-R25: bca-oslo wrote its real phone and address here; now a no-op
OLD_ADDRESS = 'Oslo, Norway'
NEW_ADDRESS = OLD_ADDRESS


def _site_settings_table():
    return sa.table(
        'site_settings',
        sa.column('id', sa.Integer),
        sa.column('contact_phone', sa.String),
        sa.column('contact_address', sa.String),
    )


def upgrade():
    # Data-only migration on the existing singleton row (id=1), seeded by the original
    # 4d2606b0c959_add_site_settings_table migration — that migration is not edited in place
    # (already applied everywhere) since Alembic never re-runs an applied migration; a real
    # database needs this follow-up UPDATE to actually pick up the new values.
    # Guarded by the OLD placeholder value so an admin's own real edit via /admin/settings
    # (if one happened in the meantime) is never silently overwritten.
    site_settings = _site_settings_table()
    op.execute(
        site_settings.update()
        .where(site_settings.c.contact_phone == OLD_PHONE)
        .values(contact_phone=NEW_PHONE, contact_address=NEW_ADDRESS)
    )


def downgrade():
    site_settings = _site_settings_table()
    op.execute(
        site_settings.update()
        .where(site_settings.c.contact_phone == NEW_PHONE)
        .values(contact_phone=OLD_PHONE, contact_address=OLD_ADDRESS)
    )
