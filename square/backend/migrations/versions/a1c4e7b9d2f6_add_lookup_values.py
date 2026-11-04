"""add lookup_values (admin-editable value drivers), seeded with expense categories

Revision ID: a1c4e7b9d2f6
Revises: d7a0b3c6e9f2
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c4e7b9d2f6'
down_revision = 'd7a0b3c6e9f2'
branch_labels = None
depends_on = None

EXPENSE_CATEGORIES = [
    ("venue", "Venue"),
    ("food", "Food"),
    ("decoration", "Decoration"),
    ("music_entertainment", "Music / Entertainment"),
    ("equipment", "Equipment"),
    ("printing", "Printing"),
    ("transportation", "Transportation"),
    ("marketing", "Marketing"),
    ("gifts", "Gifts"),
    ("supplies", "Supplies"),
    ("other", "Other"),
]


def upgrade():
    table = op.create_table(
        'lookup_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('list_key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=60), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('list_key', 'value', name='uq_lookup_values_list_value'),
    )
    op.create_index('ix_lookup_values_list_key', 'lookup_values', ['list_key'])
    op.bulk_insert(
        table,
        [
            {"list_key": "expense_category", "value": v, "label": label, "sort_order": i, "is_active": True}
            for i, (v, label) in enumerate(EXPENSE_CATEGORIES, start=1)
        ],
    )


def downgrade():
    op.drop_index('ix_lookup_values_list_key', table_name='lookup_values')
    op.drop_table('lookup_values')
