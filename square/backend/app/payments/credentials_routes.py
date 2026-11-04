"""Settings -> Payments: connect a payment provider with the square's own keys (rootsquares W16-R4, docs/plans/payment-credentials-plan.md).

Write-only: the keys are checked with the provider, stored encrypted, and never sent back. Any admin sees the status; only the square's
owner (the person the platform created the square for) may connect, replace or disconnect, because these keys move the association's money.
"""

import logging
import re

from flask import Blueprint, g, jsonify, request
from sqlalchemy import inspect, text

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.payments import credentials, stripe_gateway, vipps

logger = logging.getLogger(__name__)

admin_payment_providers_bp = Blueprint("admin_payment_providers", __name__, url_prefix="/api/admin/payments/providers")
admin_payment_providers_bp.before_request(require_role("admin"))

VIPPS_FIELDS = ("client_id", "client_secret", "subscription_key", "msn")
WEBHOOK_EVENTS = [
    "epayments.payment.authorized.v1",
    "epayments.payment.aborted.v1",
    "epayments.payment.expired.v1",
    "epayments.payment.terminated.v1",
]


@admin_payment_providers_bp.after_request
def _never_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def is_square_owner(user) -> bool:
    """The platform lists a square's owner in the `admins` table of the square's database. A single-tenant server (no such table) has no
    separate owner, so there every admin is one."""
    connection = db.session.connection()
    if not inspect(connection).has_table("admins"):
        return True
    row = db.session.execute(text("select 1 from admins where auth_user_id = :sub limit 1"), {"sub": user.auth_user_id}).first()
    return row is not None


def _view() -> dict:
    return {"can_edit": is_square_owner(g.current_user), "providers": {"vipps": credentials.status("vipps"), "stripe": credentials.status("stripe")}}


@admin_payment_providers_bp.get("")
def list_providers():
    return jsonify(_view())


def _clean_vipps(data: dict) -> tuple[dict, dict]:
    values, errors = {}, {}
    for field in VIPPS_FIELDS:
        raw = data.get(field)
        text_value = raw.strip() if isinstance(raw, str) else ""
        if not text_value:
            errors[field] = "This field is required."
        elif len(text_value) > 200 or re.search(r"\s", text_value):
            errors[field] = "This does not look like a key (no spaces, at most 200 characters)."
        else:
            values[field] = text_value
    if "msn" in values and not values["msn"].isdigit():
        errors["msn"] = "The merchant serial number is digits only."
    mode = data.get("mode")
    if mode not in credentials.MODES:
        errors["mode"] = "Choose test or production."
    values["mode"] = mode
    return values, errors


def _webhook_url() -> str | None:
    """Vipps can only call a public https address; on a local machine the webhook is simply not registered."""
    base = request.host_url.rstrip("/")
    host = request.host.split(":")[0]
    if not base.startswith("https://") or host.endswith(".localhost") or host in ("localhost", "127.0.0.1"):
        return None
    return f"{base}/api/webhooks/vipps"


@admin_payment_providers_bp.put("/vipps")
def connect_vipps():
    if not is_square_owner(g.current_user):
        return jsonify({"errors": {"_": "Only the owner of this site can connect payment accounts."}}), 403
    data = request.get_json(silent=True)
    values, errors = _clean_vipps(data if isinstance(data, dict) else {})
    if errors:
        return jsonify({"errors": errors}), 400

    mode = values.pop("mode")
    creds = credentials.VippsCredentials(values["client_id"], values["client_secret"], values["subscription_key"], values["msn"], mode)
    client = vipps.VippsClient(creds)
    try:
        client._access_token()  # the real test: Vipps must accept these keys in this environment
    except vipps.VippsError as exc:
        reason = (
            "Vipps did not accept these keys. Check the client secret and the subscription key, and that test or production matches where you copied them from."
            if exc.status_code in (400, 401, 403)
            else "Could not reach Vipps just now. Please try again in a moment."
        )
        return jsonify({"errors": {"_": reason}}), 422

    # The webhook: Vipps tells us when a payment changes. Keep the secret of an already registered webhook for the same account.
    previous = credentials.get_secret("vipps")
    webhook_secret = ""
    if previous and previous[0].get("msn") == values["msn"] and previous[0].get("client_id") == values["client_id"] and previous[1].mode == mode:
        webhook_secret = previous[0].get("webhook_secret", "")
    url = _webhook_url()
    if not webhook_secret and url:
        try:
            webhook_secret = str(client.register_webhook(url, WEBHOOK_EVENTS).get("secret") or "")
        except vipps.VippsError:
            logger.warning("Vipps webhook could not be registered for this square")
    fields = {**values, "webhook_secret": webhook_secret}
    hint = {"client_id_last4": credentials.last4(values["client_id"]), "msn": values["msn"]}
    try:
        credentials.save("vipps", fields, mode=mode, hint=hint, webhook_registered=bool(webhook_secret), user_id=g.current_user.id)
    except credentials.CredentialsError as exc:
        return jsonify({"errors": {"_": str(exc)}}), 500
    log_action(g.current_user, "payment_provider_connected", f"Connected Vipps ({mode} mode)")
    return jsonify(_view())


def _switch_off(field: str) -> None:
    from app.settings.models import get_site_settings

    settings = get_site_settings()
    if getattr(settings, field):
        setattr(settings, field, False)
        db.session.commit()


@admin_payment_providers_bp.delete("/vipps")
def disconnect_vipps():
    if not is_square_owner(g.current_user):
        return jsonify({"errors": {"_": "Only the owner of this site can disconnect payment accounts."}}), 403
    if credentials.delete("vipps"):
        _switch_off("vipps_app_public")  # a method without keys must not stay on
        log_action(g.current_user, "payment_provider_disconnected", "Disconnected Vipps")
    return jsonify(_view())


@admin_payment_providers_bp.put("/stripe")
def connect_stripe():
    if not is_square_owner(g.current_user):
        return jsonify({"errors": {"_": "Only the owner of this site can connect payment accounts."}}), 403
    data = request.get_json(silent=True)
    raw = data.get("secret_key") if isinstance(data, dict) else None
    key = raw.strip() if isinstance(raw, str) else ""
    if not key:
        return jsonify({"errors": {"secret_key": "This field is required."}}), 400
    if not key.startswith(stripe_gateway.KEY_PREFIXES) or len(key) > 300 or re.search(r"\s", key):
        return jsonify({"errors": {"secret_key": "This is not a Stripe secret key. It starts with rk_ (restricted) or sk_ (secret), then test_ or live_."}}), 400

    creds = credentials.StripeCredentials(key)
    client = stripe_gateway.StripeClient(creds)
    try:
        client.check()  # the real test: Stripe must accept the key and it must be allowed to read Checkout Sessions
    except stripe_gateway.StripeError as exc:
        reason = (
            "Stripe did not accept this key. Copy it again from Stripe (Developers, API keys)."
            if exc.status_code == 401
            else "This key is missing a permission. Tick Checkout Sessions (write), Refunds (write) and Webhook Endpoints (write) when you create the restricted key."
            if exc.status_code == 403
            else "Could not reach Stripe just now. Please try again in a moment."
        )
        return jsonify({"errors": {"_": reason}}), 422

    # The webhook: Stripe tells us when a payment completes. Keep the secret of one already registered with the same key.
    previous = credentials.get_secret("stripe")
    webhook_secret = ""
    if previous and previous[0].get("secret_key") == key:
        webhook_secret = previous[0].get("webhook_secret", "")
    base = request.host_url.rstrip("/")
    host = request.host.split(":")[0]
    public = base.startswith("https://") and not host.endswith(".localhost") and host not in ("localhost", "127.0.0.1")
    # Managed Payments (Stripe handles the tax) is the owner's choice: on needs a product tax code, off sends none.
    managed = bool(data.get("managed_payments")) if isinstance(data, dict) else False
    tax = data.get("tax_code") if isinstance(data, dict) else None
    tax = tax.strip() if isinstance(tax, str) and managed else ""
    if managed and not re.fullmatch(r"txcd_\d{8}", tax):
        return jsonify({"errors": {"tax_code": "Managed Payments needs a Stripe product tax code, like txcd_10000000."}}), 400
    typed = data.get("webhook_secret") if isinstance(data, dict) else None
    typed = typed.strip() if isinstance(typed, str) else ""
    if typed:
        # The owner pasted the signing secret from Stripe (or the Stripe CLI): it wins over an automatic registration.
        if not typed.startswith("whsec_") or len(typed) > 300 or re.search(r"\s", typed):
            return jsonify({"errors": {"webhook_secret": "This is not a Stripe signing secret. It starts with whsec_."}}), 400
        webhook_secret = typed
    if not webhook_secret and public:
        try:
            webhook_secret = str(client.register_webhook(f"{base}/api/webhooks/stripe", stripe_gateway.WEBHOOK_EVENTS).get("secret") or "")
        except stripe_gateway.StripeError:
            logger.warning("Stripe webhook could not be registered for this square")
    hint = {"key_last4": credentials.last4(key), "restricted": key.startswith("rk_")}
    try:
        credentials.save("stripe", {"secret_key": key, "webhook_secret": webhook_secret, "tax_code": tax}, mode=creds.mode, hint=hint, webhook_registered=bool(webhook_secret), user_id=g.current_user.id)
    except credentials.CredentialsError as exc:
        return jsonify({"errors": {"_": str(exc)}}), 500
    log_action(g.current_user, "payment_provider_connected", f"Connected Stripe ({creds.mode} mode)")
    return jsonify(_view())


@admin_payment_providers_bp.delete("/stripe")
def disconnect_stripe():
    if not is_square_owner(g.current_user):
        return jsonify({"errors": {"_": "Only the owner of this site can disconnect payment accounts."}}), 403
    if credentials.delete("stripe"):
        _switch_off("stripe_enabled")
        log_action(g.current_user, "payment_provider_disconnected", "Disconnected Stripe")
    return jsonify(_view())
