"""squares: the owner's request for an own sending domain, and the notices of it (ADR 095, W25-R31)

Revision ID: 0036
Revises: 0035

Five nullable columns, empty for every square: `mail_domain_request` and `mail_domain_request_local` (what the owner asked for, until staff set it
up or turn it down), `mail_domain_requested_at`, `mail_domain_help_at` (the owner asked for IT help) and `mail_domain_notified` (the last notice the
owner got about the registered domain: `ready` or `failed`, so each is sent once). Downgrade drops the columns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

COLUMNS = (
    ("mail_domain_request", sa.String(length=255)),
    ("mail_domain_request_local", sa.String(length=64)),
    ("mail_domain_requested_at", sa.DateTime(timezone=True)),
    ("mail_domain_help_at", sa.DateTime(timezone=True)),
    ("mail_domain_notified", sa.String(length=16)),
)


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    with op.batch_alter_table("squares") as batch:
        for name, kind in COLUMNS:
            if name not in have:
                batch.add_column(sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as batch:
        for name, _ in COLUMNS:
            batch.drop_column(name)
