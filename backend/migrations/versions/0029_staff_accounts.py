"""staff accounts: staff_users, staff_sessions, audit_log.actor_staff_id; today's platform admins are copied across (ADR 083, W20-R2)

Revision ID: 0029
Revises: 0028

Every user with the platform admin flag and a password becomes a staff member (same argon2 hash, no second step yet: the first staff sign-in
enrols one). An admin without a password (a provider sign-in) cannot be copied: it is named in the migration log and needs `flask staff-create`.
The flag itself stays until the end of wave 20 (migration 0030).
"""

from __future__ import annotations

import logging
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    if "staff_users" not in tables:
        op.create_table(
            "staff_users",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("totp_secret", sa.Text(), nullable=True),
            sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("totp_last_step", sa.Integer(), nullable=True),
            sa.Column("recovery_codes", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_staff_users_email", "staff_users", ["email"], unique=True)
    if "staff_sessions" not in tables:
        op.create_table(
            "staff_sessions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("staff_id", sa.Uuid(), sa.ForeignKey("staff_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("second_step_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip_tag", sa.String(length=64), nullable=True),
        )
        op.create_index("ix_staff_sessions_staff_id", "staff_sessions", ["staff_id"])
    if "actor_staff_id" not in {c["name"] for c in insp.get_columns("audit_log")}:
        op.add_column("audit_log", sa.Column("actor_staff_id", sa.Uuid(), nullable=True))
        op.create_index("ix_audit_log_actor_staff_id", "audit_log", ["actor_staff_id"])

    text_cols = lambda *names: [sa.column(n, sa.String) for n in names]  # noqa: E731
    if "is_platform_admin" not in {c["name"] for c in insp.get_columns("users")}:
        return  # a database made after the flag was dropped (0031): nobody to copy

    users = sa.table("users", *text_cols("email", "name", "password_hash"), sa.column("is_platform_admin", sa.Boolean))
    staff = sa.table("staff_users", sa.column("id", sa.Uuid), *text_cols("email", "name", "password_hash"))
    have = {r[0] for r in bind.execute(sa.select(staff.c.email))}
    for email, name, password_hash in bind.execute(sa.select(users.c.email, users.c.name, users.c.password_hash).where(users.c.is_platform_admin.is_(True))):
        if email in have:
            continue
        if not password_hash:
            log.warning("platform admin %s has no password (provider sign-in): create the staff account with `flask staff-create`", email)
            continue
        bind.execute(staff.insert().values(id=uuid.uuid4(), email=email, name=name or "", password_hash=password_hash))


def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_staff_id", table_name="audit_log")
    op.drop_column("audit_log", "actor_staff_id")
    op.drop_table("staff_sessions")
    op.drop_table("staff_users")
