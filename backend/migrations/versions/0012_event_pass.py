"""the life of an Event pass: live until, archive until, soft delete, export confirmed, reminders (W11, ADR 044)

Revision ID: 0012
Revises: 0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_DATES = ("event_started_at", "event_live_until", "event_archive_until", "event_deleted_at", "event_export_confirmed_at")


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    for name in _DATES:
        if name not in have:
            op.add_column("squares", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    if "event_reminders" not in have:
        op.add_column("squares", sa.Column("event_reminders", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("squares", "event_reminders")
    for name in reversed(_DATES):
        op.drop_column("squares", name)
