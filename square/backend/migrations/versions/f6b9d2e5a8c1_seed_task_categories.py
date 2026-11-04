"""seed task_category lookup values

Revision ID: f6b9d2e5a8c1
Revises: e5a8c1d4f7b0
Create Date: 2026-10-08 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6b9d2e5a8c1'
down_revision = 'e5a8c1d4f7b0'
branch_labels = None
depends_on = None

VALUES = [
    ("food", "Food"),
    ("cultural", "Cultural"),
    ("decoration", "Decoration"),
    ("logistics", "Logistics"),
    ("registration", "Registration"),
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
        op.execute(insert.bindparams(list_key="task_category", value=v, label=label, sort_order=i))


def downgrade():
    op.execute("DELETE FROM lookup_values WHERE list_key = 'task_category'")
