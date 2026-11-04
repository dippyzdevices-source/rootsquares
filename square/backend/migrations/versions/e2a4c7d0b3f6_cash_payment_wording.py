"""cash payments: per-event method list + admin-written cash wording

Revision ID: e2a4c7d0b3f6
Revises: d1f3b6a9c2e5
Create Date: 2026-10-09 15:00:00.000000

* events.ticket_payment_methods becomes a comma-separated list ("qr,app,cash"), so it is widened and
  the old value "both" is rewritten to "qr,app" (the code still reads "both" as "qr,app").
* events.cash_note: optional wording for Cash payers of that event.
* site_settings.cash_ticket_note / cash_membership_note: the site-wide Cash wording.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2a4c7d0b3f6'
down_revision = 'd1f3b6a9c2e5'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('events', 'ticket_payment_methods', existing_type=sa.String(length=10), type_=sa.String(length=30),
                    existing_nullable=False, existing_server_default='both', server_default='qr,app')
    op.execute("UPDATE events SET ticket_payment_methods = 'qr,app' WHERE ticket_payment_methods = 'both'")
    op.add_column('events', sa.Column('cash_note', sa.Text(), nullable=True))
    op.add_column('site_settings', sa.Column('cash_ticket_note', sa.Text(), nullable=False, server_default=''))
    op.add_column('site_settings', sa.Column('cash_membership_note', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('site_settings', 'cash_membership_note')
    op.drop_column('site_settings', 'cash_ticket_note')
    op.drop_column('events', 'cash_note')
    # Cash cannot be represented by the old three values: any list that includes it falls back to the
    # closest old setting (QR only / app only / both).
    op.execute("UPDATE events SET ticket_payment_methods = 'both' WHERE ticket_payment_methods IN ('qr,app', 'qr,app,cash', 'qr,cash,app')")
    op.execute("UPDATE events SET ticket_payment_methods = 'qr' WHERE ticket_payment_methods NOT IN ('both', 'qr', 'app')")
    op.alter_column('events', 'ticket_payment_methods', existing_type=sa.String(length=30), type_=sa.String(length=10),
                    existing_nullable=False, existing_server_default='qr,app', server_default='both')
