"""Public newsletter sign-up and unsubscribe. Unauthenticated by design; like the testimonial
submission endpoint there is no CAPTCHA/rate-limit infra, so the guardrails are: a strict email
check, a length cap, and a response that never reveals whether an address was already on the
list (no enumeration). The confirmation email is only sent when someone is newly subscribed or
re-subscribes, so repeated submissions can't be used to mail-bomb an address.
"""

import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from app.common.site import site_name
from app.common.urls import frontend_base_url
from app.email.service import get_email_service
from app.email.templates import render_newsletter_confirm_email, render_newsletter_subscribed_email
from app.extensions import db
from app.messages import service as messages_service
from app.newsletter.models import Subscriber

newsletter_bp = Blueprint("newsletter", __name__, url_prefix="/api/newsletter")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_EMAIL_LENGTH = 255


def _send_subscribed_email(subscriber: Subscriber) -> None:
    """Best effort — a failed send is logged (never the address) and never blocks sign-up."""
    try:
        unsubscribe_url = f"{frontend_base_url()}/newsletter/unsubscribe?token={subscriber.token}"
        html_body, text_body, attachments = render_newsletter_subscribed_email(
            unsubscribe_url=unsubscribe_url
        )
        get_email_service().send_email(
            to=subscriber.email,
            subject=f"You're subscribed to the {site_name()} newsletter",
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001 - best effort, see docstring
        current_app.logger.error("Newsletter confirmation email failed to send: %s", exc)


def _send_confirm_email(subscriber: Subscriber) -> None:
    """The double opt-in mail (W15-R9): the address is only on the list once its owner clicks the link. Best effort, never logs the address."""
    try:
        confirm_url = f"{frontend_base_url()}/newsletter/confirm?token={subscriber.token}"
        html_body, text_body, attachments = render_newsletter_confirm_email(confirm_url=confirm_url)
        get_email_service().send_email(
            to=subscriber.email,
            subject=f"Confirm your {site_name()} newsletter subscription",
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001 - best effort, see docstring
        current_app.logger.error("Newsletter confirm email failed to send: %s", exc)


@newsletter_bp.post("/subscribe")
def subscribe():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if (
        not isinstance(email, str)
        or not email.strip()
        or len(email.strip()) > MAX_EMAIL_LENGTH
        or not EMAIL_RE.match(email.strip())
    ):
        return jsonify({"errors": {"email": "Enter a valid email address."}}), 400
    # Consent is an explicit act: the form's submit is the consent, but an API caller must say so.
    if data.get("consent") is not True:
        return jsonify({"errors": {"consent": "Consent is required."}}), 400

    normalized = email.strip().lower()
    subscriber = Subscriber.query.filter_by(email=normalized).first()
    now = datetime.now(timezone.utc)
    send_email = False
    if subscriber is None:
        subscriber = Subscriber(email=normalized, status="pending", consented_at=now)
        db.session.add(subscriber)
        send_email = True
    elif subscriber.status == "unsubscribed":
        subscriber.status = "pending"
        subscriber.unsubscribed_at = None
        subscriber.consented_at = now
        send_email = True
    elif subscriber.status == "pending":
        # asked again before confirming: send the link again, but not more than once an hour (no mail-bombing)
        asked = subscriber.consented_at if subscriber.consented_at.tzinfo else subscriber.consented_at.replace(tzinfo=timezone.utc)
        if now - asked > timedelta(hours=1):
            subscriber.consented_at = now
            send_email = True
    db.session.commit()

    if send_email:
        _send_confirm_email(subscriber)
    # the same answer for every address, so the form never tells whether an address is already on the list
    return jsonify({"status": "pending"}), 200


@newsletter_bp.post("/confirm")
def confirm():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    subscriber = Subscriber.query.filter_by(token=token).first() if isinstance(token, str) and token else None
    if subscriber is None or subscriber.status == "unsubscribed":
        return jsonify({"error": "This confirmation link is not valid."}), 404
    if subscriber.status == "pending":
        subscriber.status = "subscribed"
        subscriber.consented_at = datetime.now(timezone.utc)
        db.session.commit()
        messages_service.unsuppress(subscriber.email)  # the confirmed click is the fresh, explicit consent: it ends an earlier opt-out (W14-R17)
        _send_subscribed_email(subscriber)
    return jsonify({"status": "subscribed"}), 200


@newsletter_bp.post("/unsubscribe")
def unsubscribe():
    # The unsubscribe page posts JSON; a mail client's one-click unsubscribe (RFC 8058) POSTs a
    # form body to the List-Unsubscribe URL, which carries the token in its query string.
    data = request.get_json(silent=True) or {}
    token = data.get("token") or request.args.get("token")
    subscriber = (
        Subscriber.query.filter_by(token=token).first() if isinstance(token, str) and token else None
    )
    if subscriber is None:
        return jsonify({"error": "This unsubscribe link is not valid."}), 404
    if subscriber.status != "unsubscribed":
        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
        db.session.commit()
    messages_service.suppress(subscriber.email)  # one opt-out for everything we send (W14-R17)
    return jsonify({"status": "unsubscribed"}), 200
