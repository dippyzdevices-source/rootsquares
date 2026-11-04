"""seed event_type lookup values

Revision ID: c3e6a9b2d5f8
Revises: b2d5f8a1c4e7
Create Date: 2026-10-08 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e6a9b2d5f8'
down_revision = 'b2d5f8a1c4e7'
branch_labels = None
depends_on = None

VALUES = [
    ("festival", "Festival"),
    ("cultural", "Cultural"),
    ("community", "Community"),
    ("other", "Other"),
]


def upgrade():
    # Idempotent: a list may already have been seeded lazily by the admin Lists page
    # (app.lookups.admin_routes._ensure_seeded) before this migration ran.
    insert = sa.text(
        "INSERT INTO lookup_values (list_key, value, label, sort_order, is_active) "
        "VALUES (:list_key, :value, :label, :sort_order, true) "
        "ON CONFLICT (list_key, value) DO NOTHING"
    )
    for i, (v, label) in enumerate(VALUES, start=1):
        op.execute(insert.bindparams(list_key="event_type", value=v, label=label, sort_order=i))


def downgrade():
    op.execute("DELETE FROM lookup_values WHERE list_key = 'event_type'")
