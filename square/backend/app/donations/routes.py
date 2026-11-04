"""Public side of the Donations module: the page's settings, giving a gift, "I have paid".

Payment methods are the ones tickets already use (Vipps app, card, Vipps QR, bank transfer, cash), switched on in Settings -> Payments. The amount comes from the
request in minor units but is validated here; nothing else is trusted from the client.
"""

import re

from flask import Blueprint, jsonify, request

from app.auth.service import resolve_user_from_token
from app.common.site import site_currency, site_name
from app.common.urls import frontend_base_url
from app.donations.models import Donation
from app.extensions import db
from app.payments import gateway, stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.bank import bank_details
from app.payments.fees import convenience_fee_for, convenience_percent
from app.payments.methods import BANK, CASH, STRIPE, VIPPS_QR
from app.payments.models import Payment
from app.settings.models import bank_transfer_available, get_site_settings, vipps_qr_available

donations_bp = Blueprint("donations", __name__, url_prefix="/api/donations")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_AMOUNT = 100  # one whole currency unit, in minor units
MAX_AMOUNT = 100_000_000  # a sanity limit, not a business rule


def available_methods() -> list[str]:
    """Which of "app", "qr", "cash" a donor may use right now (nothing is forced: none left = the page says donations are not open)."""
    settings = get_site_settings()
    methods = []
    if vipps.is_public():
        methods.append("app")
    if stripe_gateway.is_public():
        methods.append("card")
    if vipps_qr_available(settings):
        methods.append("qr")
    if bank_transfer_available(settings):
        methods.append("bank")
    if settings.cash_enabled:
        methods.append("cash")
    return methods


def suggested_amounts(settings) -> list[int]:
    return [int(p) * 100 for p in (settings.donation_amounts or "").split(",") if p.strip().isdigit()]


def _serialize(donation: Donation) -> dict:
    return {
        "reference": donation.reference,
        "amount": donation.amount,
        "currency": donation.currency,
        "status": donation.status,
        "donor_name": donation.donor_name,
        "created_at": donation.created_at.isoformat(),
    }


@donations_bp.get("/config")
def donation_config():
    settings = get_site_settings()
    methods = available_methods()
    return jsonify(
        {
            "open": bool(methods),
            "methods": methods,
            "amounts": suggested_amounts(settings),
            "min_amount": MIN_AMOUNT,
            "currency": site_currency(),
            "intro": settings.donation_intro or "",
            "thanks": settings.donation_thanks or "",
            "vipps_number": (settings.vipps_number or "").strip() if "qr" in methods else "",
            "vipps_qr_image_url": settings.vipps_qr_image_url if "qr" in methods else None,
            "bank": bank_details(settings) if "bank" in methods else None,
            "cash_note": (settings.cash_ticket_note or "").strip() if "cash" in methods else "",
            "surcharge_percent": float(convenience_percent(vipps.PROVIDER)) if "app" in methods else 0,
            "card_surcharge_percent": stripe_gateway.surcharge_percent() if "card" in methods else 0,
        }
    )


def _optional_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return resolve_user_from_token(header.removeprefix("Bearer ").strip())


@donations_bp.post("")
def give():
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    name = data.get("donor_name")
    email = data.get("donor_email")
    amount = data.get("amount")
    method = data.get("payment_method")
    message = data.get("message")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        errors["donor_name"] = "This field is required."
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        errors["donor_email"] = "Enter a valid email address."
    if not isinstance(amount, int) or isinstance(amount, bool) or not MIN_AMOUNT <= amount <= MAX_AMOUNT:
        errors["amount"] = "Enter an amount of at least 1."
    if message is not None and (not isinstance(message, str) or len(message) > 1000):
        errors["message"] = "At most 1000 characters."
    if method not in available_methods():
        errors["payment_method"] = "Choose how you want to give."
    if errors:
        return jsonify({"errors": errors}), 400

    user = _optional_user()
    donation = Donation(
        reference="PENDING",
        user_id=user.id if user else None,
        donor_name=name.strip(),
        donor_email=email.strip(),
        anonymous=bool(data.get("anonymous")),
        message=(message or "").strip() or None,
        amount=amount,
        currency=site_currency(),
    )
    db.session.add(donation)
    db.session.flush()
    donation.reference = f"DON-{donation.created_at.year}-{donation.id:06d}"

    provider = {"app": vipps.PROVIDER, "card": STRIPE, "qr": VIPPS_QR, "bank": BANK, "cash": CASH}[method]
    online = provider in gateway.ONLINE_PROVIDERS
    surcharge = convenience_fee_for(provider, amount) if online else 0
    payment = Payment(
        payment_type="donation",
        donation_id=donation.id,
        provider=provider,
        amount=amount + surcharge,
        surcharge_amount=surcharge or None,
        currency=donation.currency,
        status="initiated" if online else "pending",
    )
    db.session.add(payment)
    db.session.flush()
    payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"

    body = _serialize(donation)
    if online:
        try:
            redirect_url = gateway.start_payment(
                payment, f"{frontend_base_url()}/donate/thanks?ref={{ref}}", f"{site_name()} gift {donation.reference}"
            )
        except GatewayError:
            db.session.rollback()  # nothing is left behind if the provider refuses
            return jsonify({"error": "Could not start the card payment. Please try again." if method == "card" else "Could not start the Vipps payment. Please try again."}), 502
        body["redirect_url"] = redirect_url
        body["surcharge_amount"] = payment.surcharge_amount or 0
    db.session.commit()
    return jsonify(body), 201


@donations_bp.post("/<reference>/confirm-payment")
def confirm_payment(reference: str):
    """The donor says they paid (Vipps QR or bank transfer): the gift waits for an admin to check that the money arrived."""
    data = request.get_json(silent=True) or {}
    donation = Donation.query.filter_by(reference=reference).first()
    if donation is None or donation.donor_email.lower() != str(data.get("email", "")).strip().lower():
        return jsonify({"error": "Donation not found"}), 404
    if donation.status != "pending":
        return jsonify({"error": "This gift is not waiting for a payment report."}), 409
    donation.status = "pending_verification"
    db.session.commit()
    return jsonify(_serialize(donation))
