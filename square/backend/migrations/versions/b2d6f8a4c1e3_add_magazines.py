"""add magazines

Revision ID: b2d6f8a4c1e3
Revises: a1c9e5d7b3f2
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


revision = "b2d6f8a4c1e3"
down_revision = "a1c9e5d7b3f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "magazines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("issue_label", sa.String(length=100)),
        sa.Column("issue_date", sa.Date()),
        sa.Column("description", sa.String(length=1000)),
        sa.Column("pdf_url", sa.String(length=500)),
        sa.Column("cover_url", sa.String(length=500)),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_magazines_slug", "magazines", ["slug"], unique=True)
    op.create_index("ix_magazines_issue_date", "magazines", ["issue_date"])
    op.create_index("ix_magazines_published", "magazines", ["published"])


def downgrade():
    op.drop_index("ix_magazines_published", table_name="magazines")
    op.drop_index("ix_magazines_issue_date", table_name="magazines")
    op.drop_index("ix_magazines_slug", table_name="magazines")
    op.drop_table("magazines")
