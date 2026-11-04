"""Public "support this event" endpoints — a donation (pay now) or a sponsorship enquiry. Open only
while the event is published and not over. No account needed.

Donations absorb the transaction fee: the donor is charged exactly the amount they typed (no
convenience fee); the provider's processing fee is saved on the Payment when it is paid and shows
up under the event's Expenses (see _fees_by_provider in admin_routes.py).

* Vipps App: a real Vipps payment; the contribution turns `paid` when Vipps confirms it
  (vipps._sync_event_donation_payment). Same return page as tickets (`kind=donation`).
* Vipps QR: the donor pays the static QR/number and says so; the contribution stays `pending`
  until an admin marks it received on the accounting page. No Payment row (nothing to reconcile
  automatically).
* Sponsorship: an enquiry only (contact details + requirements, `pending`); payment is arranged
  offline and the admin marks it received.
"""

import re
from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from app.accounting.models import EventContribution
from app.common.site import site_currency
from app.common.urls import frontend_base_url
from app.events.models import Event
from app.extensions import db
from app.payments import gateway, stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.methods import STRIPE, VIPPS_QR
from app.payments.models import Payment
from app.settings.models import get_site_settings

event_support_bp = Blueprint("event_support", __name__, url_prefix="/api/events/<slug>/support")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ANONYMOUS = "Anonymous"
MIN_DONATION = 1000  # 10 kr, in øre
MAX_DONATION = 10_000_000  # 100 000 kr


def event_is_over(event: Event) -> bool:
    """Same rule as the frontend's event phase: an event with no end time runs to the end of its start day."""
    start = event.start_datetime if event.start_datetime.tzinfo else event.start_datetime.replace(tzinfo=timezone.utc)
    end = event.end_datetime
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    over = end if end is not None else start.replace(hour=23, minute=59, second=59)
    return over < datetime.now(timezone.utc)


def _open_event(slug: str):
    """(event, None) when it is published and not over, else (None, (response, status))."""
    event = Event.query.filter_by(slug=slug, published=True).first()
    if event is None:
        return None, (jsonify({"error": "Event not found"}), 404)
    if event_is_over(event):
        return None, (jsonify({"error": "This event is over, so it no longer accepts donations or sponsorships."}), 409)
    return event, None


def donation_methods() -> list[str]:
    methods = []
    if vipps.is_public():
        methods.append(vipps.PROVIDER)
    if stripe_gateway.is_public():
        methods.append(STRIPE)
    if get_site_settings().vipps_qr_enabled:
        methods.append(VIPPS_QR)
    return methods


@event_support_bp.get("/options")
def options(slug: str):
    event = Event.query.filter_by(slug=slug, published=True).first()
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    is_open = not event_is_over(event)
    methods = donation_methods()
    return jsonify(
        {
            "open": is_open,
            "donations_open": is_open and bool(methods),
            "sponsorships_open": is_open,
            "payment_methods": methods,
        }
    )


def _clean_text(value, limit: int, errors: dict, field: str, *, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors[field] = "This field is required."
        return None
    if not isinstance(value, str):
        errors[field] = "Must be text."
        return None
    if len(value.strip()) > limit:
        errors[field] = f"Must be at most {limit} characters."
        return None
    return value.strip()


def _clean_email(value, errors: dict, *, required: bool) -> str | None:
    email = _clean_text(value, 255, errors, "email", required=required)
    if email and not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
        return None
    return email


@event_support_bp.post("/donations")
def donate(slug: str):
    event, error = _open_event(slug)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}

    name = _clean_text(data.get("name"), 200, errors, "name") or ANONYMOUS
    email = _clean_email(data.get("email"), errors, required=False)
    amount = data.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not (MIN_DONATION <= amount <= MAX_DONATION):
        errors["amount"] = f"Enter an amount between {MIN_DONATION // 100} and {MAX_DONATION // 100} {site_currency()}."
    method = data.get("payment_method")
    if method not in donation_methods():
        errors["payment_method"] = "That payment method is not available."
    if errors:
        return jsonify({"errors": errors}), 400

    contribution = EventContribution(
        event_id=event.id, kind="donation", name=name, email=email, amount=int(amount),
        date=date.today(), payment_method=method, status="pending",
    )
    db.session.add(contribution)

    redirect_url = None
    if method in gateway.ONLINE_PROVIDERS:
        # No convenience fee: the donor pays exactly what they typed.
        payment = Payment(
            payment_type="event_donation", provider=method, amount=contribution.amount,
            currency=site_currency(), status="initiated",
        )
        db.session.add(payment)
        db.session.flush()
        payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
        contribution.payment_id = payment.id
        try:
            redirect_url = gateway.start_payment(
                payment, f"{frontend_base_url()}/orders/vipps-return?ref={{ref}}&kind=donation", f"Donation - {event.title}"[:100]
            )
        except GatewayError:
            db.session.rollback()
            return jsonify({"error": "Could not start the card payment. Please try again." if method == STRIPE else "Could not start the Vipps payment. Please try again."}), 502

    db.session.commit()
    return jsonify({"payment_method": method, "redirect_url": redirect_url}), 201


@event_support_bp.post("/sponsorships")
def sponsor(slug: str):
    event, error = _open_event(slug)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}

    name = _clean_text(data.get("name"), 200, errors, "name", required=True)
    contact_name = _clean_text(data.get("contact_name"), 200, errors, "contact_name", required=True)
    email = _clean_email(data.get("email"), errors, required=True)
    phone = _clean_text(data.get("phone"), 30, errors, "phone")
    website = _clean_text(data.get("website"), 300, errors, "website")
    if website and not re.match(r"^https?://", website, re.I):
        errors["website"] = "Must start with http:// or https://"
    requirements = _clean_text(data.get("requirements"), 2000, errors, "requirements")
    amount = data.get("amount")
    if amount in (None, ""):
        amount = None
    elif isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        errors["amount"] = "Must be a number greater than zero."
    if errors:
        return jsonify({"errors": errors}), 400

    db.session.add(
        EventContribution(
            event_id=event.id, kind="sponsorship", name=name, contact_name=contact_name, email=email,
            phone=phone, website=website, requirements=requirements,
            amount=int(amount) if amount is not None else None, date=date.today(), status="pending",
        )
    )
    db.session.commit()
    return jsonify({"ok": True}), 201
