"""add description to membership_types (seeded from the old hardcoded blurbs)

Revision ID: b8d1f4a7c0e3
Revises: a7c0e3f6b9d2
Create Date: 2026-10-08 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8d1f4a7c0e3'
down_revision = 'a7c0e3f6b9d2'
branch_labels = None
depends_on = None

DESCRIPTIONS = {
    "adult": "For one adult member of the community.",
    "child": "For a child, linked to a parent's adult membership.",
    "individual": "For one adult member of the community.",
    "family": "Covers a household — partner and children included.",
    "student": "A reduced rate for full-time students.",
    "senior": "A reduced rate for senior members.",
    "lifetime": "A one-time membership that never needs renewing.",
}


def upgrade():
    op.add_column('membership_types', sa.Column('description', sa.String(length=300), nullable=True))
    table = sa.table('membership_types', sa.column('name', sa.String), sa.column('description', sa.String))
    for name, text in DESCRIPTIONS.items():
        op.execute(table.update().where(table.c.name == name).values(description=text))


def downgrade():
    op.drop_column('membership_types', 'description')
