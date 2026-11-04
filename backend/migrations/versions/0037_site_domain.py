"""squares: the own website domain (ADR 098, W26-R4)

Revision ID: 0037
Revises: 0036

Three nullable columns, empty for every square: `site_domain_request` (the domain the owner asked for, until staff add it on the host or turn it down),
`site_domain_requested_at` and `site_domain` (the active own domain, unique; the default `<slug>.<suffix>` in `domain` keeps working).
Downgrade drops the columns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}
    with op.batch_alter_table("squares") as batch:
        if "site_domain_request" not in have:
            batch.add_column(sa.Column("site_domain_request", sa.String(length=255), nullable=True))
        if "site_domain_requested_at" not in have:
            batch.add_column(sa.Column("site_domain_requested_at", sa.DateTime(timezone=True), nullable=True))
        if "site_domain" not in have:
            batch.add_column(sa.Column("site_domain", sa.String(length=255), nullable=True))
            batch.create_unique_constraint("uq_squares_site_domain", ["site_domain"])


def downgrade() -> None:
    with op.batch_alter_table("squares") as batch:
        batch.drop_constraint("uq_squares_site_domain", type_="unique")
        batch.drop_column("site_domain")
        batch.drop_column("site_domain_requested_at")
        batch.drop_column("site_domain_request")
