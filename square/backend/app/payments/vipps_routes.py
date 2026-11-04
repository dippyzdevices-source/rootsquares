"""Public Vipps webhook endpoint. Vipps cannot send a login token, so the request is authenticated
by its HMAC signature instead (app.payments.vipps.verify_webhook_signature), and the body is
never trusted for anything beyond "which payment to re-check" — sync_vipps_payment() asks Vipps
for the real state.
"""

import logging

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.payments import credentials, gateway, stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.fees import convenience_percent
from app.payments.models import Payment

logger = logging.getLogger(__name__)

vipps_webhooks_bp = Blueprint("vipps_webhooks", __name__, url_prefix="/api/webhooks")
vipps_public_bp = Blueprint("vipps_public", __name__, url_prefix="/api/payments")


@vipps_webhooks_bp.post("/vipps")
def vipps_webhook():
    raw = request.get_data()
    path = request.full_path.rstrip("?")
    creds = credentials.get_vipps()  # this square's own webhook secret; none stored = nothing can be authenticated
    if not vipps.verify_webhook_signature(creds.webhook_secret if creds else "", "POST", path, request.headers, raw):
        logger.warning("Vipps webhook rejected: bad signature")
        return "", 401

    body = request.get_json(silent=True)
    reference = body.get("reference") if isinstance(body, dict) else None
    payment = (
        Payment.query.filter_by(provider=vipps.PROVIDER, provider_transaction_id=reference).first()
        if isinstance(reference, str)
        else None
    )
    if payment is None:
        # Unknown reference (e.g. a payment from another environment) — acknowledge so Vipps
        # doesn't keep retrying; there is nothing for us to do.
        return "", 200

    try:
        vipps.sync_vipps_payment(payment)
    except vipps.VippsError:
        db.session.rollback()
        # 5xx makes Vipps retry later.
        return "", 502
    return "", 200


@vipps_public_bp.get("/vipps-app")
def vipps_app_config():
    """Whether "Pay in the Vipps app" is offered, and its fee, for the checkout page."""
    return jsonify({"enabled": vipps.is_public(), "surcharge_percent": float(convenience_percent(vipps.PROVIDER))})


@vipps_public_bp.post("/vipps-return")
def vipps_return():
    """A (possibly guest) customer lands back from Vipps with the payment's random reference.
    Possession of that reference is the only credential, and it grants nothing beyond "re-check
    this payment with Vipps" — the result comes from Vipps, never from this request."""
    body = request.get_json(silent=True) or {}
    reference = body.get("reference")
    payment = (
        Payment.query.filter(Payment.provider.in_(gateway.ONLINE_PROVIDERS), Payment.provider_transaction_id == reference).first()
        if isinstance(reference, str)
        else None
    )
    if payment is None:
        return jsonify({"error": "Payment not found"}), 404
    try:
        if body.get("cancelled") and payment.provider == stripe_gateway.PROVIDER and payment.status == "initiated":
            stripe_gateway.StripeClient().abandon(payment.provider_transaction_id)  # the customer left the Stripe page: close it unless it was paid
        payment = gateway.sync(payment)
    except GatewayError:
        db.session.rollback()
        return jsonify({"error": "Could not check the payment with the payment provider. Please try again."}), 502
    order_number = None
    if payment.order_id:
        from app.orders.models import Order

        order = db.session.get(Order, payment.order_id)
        order_number = order.order_number if order else None
    donation_reference = None
    if payment.donation_id:
        from app.donations.models import Donation

        donation = db.session.get(Donation, payment.donation_id)
        donation_reference = donation.reference if donation else None
    body = {"status": payment.status, "order_number": order_number, "provider": payment.provider}
    if donation_reference:
        body["donation_reference"] = donation_reference
    return jsonify(body)


stripe_webhooks_bp = Blueprint("stripe_webhooks", __name__, url_prefix="/api/webhooks")
stripe_public_bp = Blueprint("stripe_public", __name__, url_prefix="/api/payments")


@stripe_webhooks_bp.post("/stripe")
def stripe_webhook():
    """Stripe tells us a Checkout Session changed. Authenticated by the signature with THIS square's own signing secret; the body is never
    trusted beyond "which payment to re-check" - the sync asks Stripe for the real state."""
    creds = credentials.get_stripe()
    event = stripe_gateway.verify_webhook(request.get_data(), request.headers.get("Stripe-Signature", ""), creds.webhook_secret if creds else "")
    if event is None:
        logger.warning("Stripe webhook rejected: bad signature")
        return "", 401
    try:
        session_id = event["data"]["object"]["id"]  # a Stripe event is an object, not a dict
    except (KeyError, TypeError):
        session_id = None
    payment = (
        Payment.query.filter_by(provider=stripe_gateway.PROVIDER, provider_transaction_id=session_id).first()
        if isinstance(session_id, str)
        else None
    )
    if payment is None:
        return "", 200  # not one of ours (another environment): acknowledge so Stripe stops retrying
    try:
        gateway.sync(payment)
    except GatewayError:
        db.session.rollback()
        return "", 502  # Stripe retries later
    return "", 200


@stripe_public_bp.get("/stripe")
def stripe_config():
    """Whether "Pay by card" is offered, and its fee, for the checkout pages."""
    return jsonify({"enabled": stripe_gateway.is_public(), "surcharge_percent": stripe_gateway.surcharge_percent()})
