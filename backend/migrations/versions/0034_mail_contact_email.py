"""squares.mail_contact_email: where the square's mail goes and where replies to it go (ADR 093, W25-R9)

Revision ID: 0034
Revises: 0033

One nullable column. Empty (null) for every existing square: the square server then falls back to the square's public contact address and, last, to the
server's CONTACT_EMAIL, so nothing changes until an owner sets it. Downgrade drops the column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "mail_contact_email" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("squares")}:
        return
    with op.batch_alter_table("squares") as batch:
        batch.add_column(sa.Column("mail_contact_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("squares") as batch:
        batch.drop_column("mail_contact_email")
