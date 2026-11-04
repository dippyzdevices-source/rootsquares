"""The donation receipt: best effort, a failed send is logged and never blocks the payment (same rule as app/orders/emails.py)."""

from flask import current_app

from app.common.site import site_name
from app.donations.models import Donation
from app.email.service import get_email_service
from app.email.templates import render_donation_receipt_email


def send_donation_receipt_email(donation: Donation) -> None:
    from app.settings.models import get_site_settings

    html_body, text_body, attachments = render_donation_receipt_email(
        donation=donation, thanks=(get_site_settings().donation_thanks or "").strip()
    )
    try:
        get_email_service().send_email(
            to=donation.donor_email,
            subject=f"Thank you for your gift to {site_name()}",
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001 - money has already changed hands
        current_app.logger.error("Donation receipt email failed to send: %s", exc)
