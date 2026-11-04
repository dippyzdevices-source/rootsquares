"""squares: the square's own sending domain at Resend (ADR 091, W25-R24)

Revision ID: 0035
Revises: 0034

Five nullable columns, all empty for every square: `mail_domain` (what the owner typed, for example `mail.theirassociation.org`),
`mail_domain_id` (Resend's id of it), `mail_domain_status` (Resend's status: not_started, pending, verified, ...), `mail_domain_records` (the DNS records
Resend asked for, JSON; not secret) and `mail_from_local` (the part before the @ that the owner chose). The square server sends from `<local>@<domain>`
only while the status is `verified` and the package allows it. Downgrade drops the columns (every square goes back to the shared sending domain;
the domain at Resend is not touched).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

COLUMNS = (
    ("mail_domain", sa.String(length=255)),
    ("mail_domain_id", sa.String(length=64)),
    ("mail_domain_status", sa.String(length=24)),
    ("mail_domain_records", sa.Text()),
    ("mail_from_local", sa.String(length=64)),
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
