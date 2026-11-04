"""add members.parent_member_id

Revision ID: f6b0d3e8a5c7
Revises: e5a9c2d7f4b6
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa


revision = "f6b0d3e8a5c7"
down_revision = "e5a9c2d7f4b6"
branch_labels = None
depends_on = None

FK_NAME = "fk_members_parent_member_id_members"


def upgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_member_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_members_parent_member_id", ["parent_member_id"], unique=False)
        batch_op.create_foreign_key(
            FK_NAME, "members", ["parent_member_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.drop_index("ix_members_parent_member_id")
        batch_op.drop_column("parent_member_id")
