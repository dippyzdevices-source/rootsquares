"""add founders

Revision ID: d5f1b3a7c942
Revises: c4e8a1d92f36
Create Date: 2026-09-29 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5f1b3a7c942'
down_revision = 'c4e8a1d92f36'
branch_labels = None
depends_on = None

# The four entries that were hardcoded in HeritageView.vue. Portraits are NOT seeded (the old
# /founders/*.jpg static files were removed) — upload them from the admin form. Quotes are still placeholder text — an admin replaces them from Admin -> Content -> Founders.
# rootsquares change (W6-R38): bca-oslo seeded its four real founders' names and quotes here. A square must not start with another
# organisation's people, so nothing is seeded; the admin adds founders in /admin (or the module is removed, docs/reference/square-hardcodings.md item 11).
SEED: list = []


def upgrade():
    founders = op.create_table(
        'founders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('sub_name', sa.String(length=200), nullable=True),
        sa.Column('role', sa.String(length=200), nullable=False),
        sa.Column('quote', sa.Text(), nullable=False),
        sa.Column('portrait_url', sa.String(length=500), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_founders_is_active', 'founders', ['is_active'])
    op.bulk_insert(
        founders,
        [
            {"name": n, "role": r, "portrait_url": p, "display_order": o, "quote": q, "is_active": True}
            for n, r, p, o, q in SEED
        ],
    )


def downgrade():
    op.drop_index('ix_founders_is_active', table_name='founders')
    op.drop_table('founders')
