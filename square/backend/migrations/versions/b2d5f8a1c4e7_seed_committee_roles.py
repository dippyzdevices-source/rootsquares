"""seed committee_role lookup values

Revision ID: b2d5f8a1c4e7
Revises: a1c4e7b9d2f6
Create Date: 2026-10-08 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2d5f8a1c4e7'
down_revision = 'a1c4e7b9d2f6'
branch_labels = None
depends_on = None

ROLES = [
    ("president", "President"),
    ("vice_president", "Vice President"),
    ("general_secretary", "General Secretary"),
    ("assistant_secretary", "Assistant Secretary"),
    ("cultural_secretary", "Cultural Secretary"),
    ("food_secretary", "Food Secretary"),
    ("food_committee", "Food Committee"),
    ("treasurer", "Treasurer"),
    ("assistant_treasurer", "Assistant Treasurer"),
    ("public_relations_officer", "Public Relations Officer"),
    ("event_coordinator", "Event Coordinator"),
    ("committee_member", "Committee Member"),
    ("media_coordinator", "Media Coordinator"),
    ("advisor", "Advisor"),
]


def upgrade():
    # Idempotent: a list may already have been seeded lazily by the admin Lists page
    # (app.lookups.admin_routes._ensure_seeded) before this migration ran.
    insert = sa.text(
        "INSERT INTO lookup_values (list_key, value, label, sort_order, is_active) "
        "VALUES (:list_key, :value, :label, :sort_order, true) "
        "ON CONFLICT (list_key, value) DO NOTHING"
    )
    for i, (v, label) in enumerate(ROLES, start=1):
        op.execute(insert.bindparams(list_key="committee_role", value=v, label=label, sort_order=i))


def downgrade():
    op.execute("DELETE FROM lookup_values WHERE list_key = 'committee_role'")
