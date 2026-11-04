"""seed fixed (wording-only) lookup lists: statuses, providers, roles, age categories

Revision ID: c9e2a5d8b1f4
Revises: b8d1f4a7c0e3
Create Date: 2026-10-09 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9e2a5d8b1f4'
down_revision = 'b8d1f4a7c0e3'
branch_labels = None
depends_on = None

LISTS = {
    "payment_status": [
        ("pending", "Pending"),
        ("pending_verification", "Pending verification"),
        ("initiated", "At Vipps"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially refunded"),
    ],
    "payment_provider": [
        ("manual", "Manual"),
        ("vipps", "Vipps QR (manual)"),
        ("vipps_app", "Vipps App"),
        ("stripe", "Stripe"),
    ],
    "payment_type": [
        ("event_ticket", "Ticket"),
        ("membership", "Membership"),
        ("vipps_test", "Vipps test"),
    ],
    "ticket_status": [
        ("valid", "Not checked in yet"),
        ("used", "Checked in"),
        ("void", "Cancelled"),
    ],
    "membership_status": [
        ("pending", "Pending"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("suspended", "Suspended"),
    ],
    "news_status": [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ],
    "newsletter_status": [
        ("subscribed", "Subscribed"),
        ("unsubscribed", "Unsubscribed"),
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
    ],
    "testimonial_status": [
        ("pending", "Pending review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ],
    "user_role": [
        ("member", "Member"),
        ("volunteer", "Volunteer"),
        ("admin", "Admin"),
    ],
    "ticket_age_category": [
        ("adult", "Adult"),
        ("child", "Child"),
        ("other", "Other"),
    ],
    "audit_action": [
        ("user_role_changed", "Role changed"),
        ("membership_status_changed", "Membership status changed"),
        ("order_marked_paid", "Order marked paid"),
        ("order_rejected", "Order rejected"),
        ("order_cancelled", "Order cancelled"),
        ("settings_updated", "Settings updated"),
        ("event_created", "Event created"),
        ("event_updated", "Event updated"),
        ("event_deleted", "Event deleted"),
        ("coupon_created", "Coupon created"),
        ("coupon_updated", "Coupon updated"),
        ("gallery_album_deleted", "Gallery album deleted"),
        ("gallery_media_deleted", "Gallery media deleted"),
        ("news_deleted", "News deleted"),
        ("ticket_type_deleted", "Ticket type deleted"),
        ("payment_refunded", "Payment refunded"),
        ("payment_confirmed", "Payment confirmed"),
        ("payment_rejected", "Payment rejected"),
        ("committee_member_deleted", "Committee member deleted"),
        ("founder_deleted", "Founder deleted"),
        ("sponsor_deleted", "Sponsor deleted"),
        ("magazine_deleted", "Magazine deleted"),
        ("expense_deleted", "Expense deleted"),
        ("lookup_value_changed", "List value changed"),
        ("membership_drive_signup", "Membership drive signup"),
        ("members_merged", "Members merged"),
        ("newsletter_sent", "Newsletter sent"),
        ("newsletter_scheduled", "Newsletter scheduled"),
        ("membership_reminder_sent", "Membership reminder sent"),
        ("membership_request_removed", "Membership request removed"),
    ],
}


def upgrade():
    # Idempotent: the admin Lists page may already have seeded a list lazily.
    insert = sa.text(
        "INSERT INTO lookup_values (list_key, value, label, sort_order, is_active) "
        "VALUES (:list_key, :value, :label, :sort_order, true) "
        "ON CONFLICT (list_key, value) DO NOTHING"
    )
    for list_key, values in LISTS.items():
        for i, (v, label) in enumerate(values, start=1):
            op.execute(insert.bindparams(list_key=list_key, value=v, label=label, sort_order=i))


def downgrade():
    keys = ", ".join("'%s'" % k for k in LISTS)
    op.execute("DELETE FROM lookup_values WHERE list_key IN (" + keys + ")")
