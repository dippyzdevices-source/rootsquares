"""support access: grants, requests and sessions (ADR 089, W23-R64)

Revision ID: 0032
Revises: 0031

Three new tables, nothing else changes. A grant is the owner's permission (for how long, which scopes, whether staff may change things); a request is a
staff member asking for one; a session is one use of a grant by a staff member. Downgrade drops the three tables (and so every grant and session).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    if "support_grants" not in have:
        op.create_table(
            "support_grants",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("square_id", sa.Uuid(), sa.ForeignKey("squares.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("granted_by", sa.Uuid(), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("scopes", sa.JSON(), nullable=False),
            sa.Column("allow_changes", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("note", sa.String(length=300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ending_notice_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "support_requests" not in have:
        op.create_table(
            "support_requests",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("square_id", sa.Uuid(), sa.ForeignKey("squares.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("staff_id", sa.Uuid(), nullable=False),
            sa.Column("staff_name", sa.String(length=120), nullable=False),
            sa.Column("note", sa.String(length=300), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("grant_id", sa.Uuid(), nullable=True),
        )
    if "support_sessions" not in have:
        op.create_table(
            "support_sessions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("support_grants.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("staff_id", sa.Uuid(), nullable=False),
            sa.Column("staff_name", sa.String(length=120), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_by", sa.String(length=12), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("support_sessions")
    op.drop_table("support_requests")
    op.drop_table("support_grants")
