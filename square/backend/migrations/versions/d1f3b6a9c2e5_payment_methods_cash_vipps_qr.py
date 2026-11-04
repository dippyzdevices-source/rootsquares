"""payment methods: Cash, Vipps QR, Vipps App (rename old 'manual'/'vipps' to 'vipps_qr')

Revision ID: d1f3b6a9c2e5
Revises: c9e2a5d8b1f4
Create Date: 2026-10-09 12:00:00.000000

Before this, a payment made by hand was stored as "manual" (ticket QR payments and membership-drive
payments) or "vipps" (membership QR payments). All of those were the Vipps QR flow — Cash did not
exist as a method — so they all become "vipps_qr". Also adds the two admin switches for the
manual-approval methods and updates the 'payment_provider' list (Cash, Vipps-QR, Vipps-App, Stripe).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1f3b6a9c2e5'
down_revision = 'c9e2a5d8b1f4'
branch_labels = None
depends_on = None

LIST_KEY = "payment_provider"
NEW_VALUES = [("cash", "Cash"), ("vipps_qr", "Vipps-QR"), ("vipps_app", "Vipps-App"), ("stripe", "Stripe")]


def upgrade():
    op.add_column('site_settings', sa.Column('vipps_qr_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('site_settings', sa.Column('cash_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute("UPDATE payments SET provider = 'vipps_qr' WHERE provider IN ('manual', 'vipps')")

    # The old list rows (manual / vipps) go away; the four new ones are added and ordered. Safe to
    # re-run: an admin may already have opened the list (which seeds it) before this ran.
    op.execute(sa.text("DELETE FROM lookup_values WHERE list_key = :k AND value IN ('manual', 'vipps')").bindparams(k=LIST_KEY))
    insert = sa.text(
        "INSERT INTO lookup_values (list_key, value, label, sort_order, is_active) "
        "VALUES (:k, :v, :l, :o, true) ON CONFLICT (list_key, value) DO UPDATE SET sort_order = :o"
    )
    for order, (value, label) in enumerate(NEW_VALUES, start=1):
        op.execute(insert.bindparams(k=LIST_KEY, v=value, l=label, o=order))
    # Spelling change only where an admin has not already reworded the label.
    op.execute(sa.text("UPDATE lookup_values SET label = 'Vipps-App' WHERE list_key = :k AND value = 'vipps_app' AND label = 'Vipps App'").bindparams(k=LIST_KEY))


def downgrade():
    # Lossy by nature (cash payments cannot exist before this migration): everything goes back to "manual".
    op.execute("UPDATE payments SET provider = 'manual' WHERE provider IN ('vipps_qr', 'cash')")
    op.execute(sa.text("DELETE FROM lookup_values WHERE list_key = :k AND value IN ('cash', 'vipps_qr')").bindparams(k=LIST_KEY))
    old = sa.text(
        "INSERT INTO lookup_values (list_key, value, label, sort_order, is_active) "
        "VALUES (:k, :v, :l, :o, true) ON CONFLICT (list_key, value) DO NOTHING"
    )
    for order, (value, label) in enumerate([("manual", "Manual"), ("vipps", "Vipps QR (manual)")], start=1):
        op.execute(old.bindparams(k=LIST_KEY, v=value, l=label, o=order))
    op.drop_column('site_settings', 'cash_enabled')
    op.drop_column('site_settings', 'vipps_qr_enabled')
