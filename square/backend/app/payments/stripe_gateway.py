"""Card payments through Stripe Checkout, with the square's OWN Stripe account (rootsquares W16-R6, docs/plans/payment-credentials-plan.md).

Same shape as the Vipps client so the payment code is written once (app/payments/gateway.py): `create_payment` gives a hosted Checkout page,
`get_payment` answers in the Vipps words the sync code already understands (paid -> "AUTHORIZED", expired -> "EXPIRED", otherwise "CREATED"),
`capture` does nothing (Checkout takes the money at once), `cancel` expires an open session or refunds a paid one, `refund` refunds.
`Payment.provider_transaction_id` holds the Checkout Session id. The keys come only from the square's stored credentials; there is no fallback.
"""

import hashlib
import logging

import stripe

from app.payments import credentials
from app.payments.errors import GatewayError
from app.payments.fees import convenience_percent
from app.settings.models import get_site_settings

logger = logging.getLogger(__name__)

PROVIDER = "stripe"
# Two-decimal currencies Stripe Checkout takes with our integer minor units (zero-decimal ones such as JPY would need other maths).
CURRENCIES = {"NOK", "SEK", "DKK", "EUR", "USD", "GBP", "CHF", "CAD", "AUD", "NZD", "PLN", "CZK", "INR", "SGD", "HKD"}
WEBHOOK_EVENTS = ["checkout.session.completed", "checkout.session.expired", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed"]
KEY_PREFIXES = ("sk_test_", "sk_live_", "rk_test_", "rk_live_")


class StripeError(GatewayError):
    """A Stripe call failed (network error or a refusal)."""


def is_enabled() -> bool:
    """Whether THIS square has connected its own Stripe account. There is no server-wide fallback."""
    return credentials.get_stripe() is not None


def is_public() -> bool:
    """Whether customers may choose to pay by card: keys connected, the admin switch on, and a currency Stripe takes."""
    from app.common.site import site_currency

    return is_enabled() and site_currency() in CURRENCIES and bool(get_site_settings().stripe_enabled)


def surcharge_percent() -> float:
    return float(convenience_percent(PROVIDER))


def _wrap(exc: Exception) -> StripeError:
    """Never put the provider's message (it can echo part of a key) into our errors or logs: only the kind of failure."""
    if isinstance(exc, stripe.AuthenticationError):
        return StripeError("Stripe did not accept this key", 401)
    if isinstance(exc, stripe.PermissionError):
        return StripeError("This Stripe key lacks a permission", 403)
    if isinstance(exc, stripe.InvalidRequestError):
        return StripeError("Stripe refused the request", 400)
    if isinstance(exc, stripe.RateLimitError):
        return StripeError("Stripe is busy, try again", 429)
    return StripeError("Could not reach Stripe")


class StripeClient:
    def __init__(self, creds: "credentials.StripeCredentials | None" = None):
        creds = creds or credentials.get_stripe()
        if creds is None:
            raise StripeError("Stripe is not connected for this square")
        self._client = stripe.StripeClient(creds.secret_key, max_network_retries=1)
        self._tax_code = creds.tax_code

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except stripe.StripeError as exc:
            # Only facts that cannot hold a secret: the kind, HTTP status, Stripe's error code and the name of the offending parameter.
            logger.warning("Stripe call failed: %s status=%s code=%s param=%s", type(exc).__name__, getattr(exc, "http_status", None), getattr(exc, "code", None), getattr(exc, "param", None))
            raise _wrap(exc) from None

    # -- the connection test ---------------------------------------------------------------
    def check(self) -> None:
        """A cheap authenticated read that needs a permission we need anyway (Checkout Sessions): proves the key is valid and usable."""
        self._call(self._client.v1.checkout.sessions.list, params={"limit": 1})

    # -- Checkout --------------------------------------------------------------------------
    def create_payment(self, reference: str, amount: int, return_url: str, description: str) -> dict:
        from app.common.site import site_currency

        params = {
            "mode": "payment",
            "client_reference_id": reference,
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {"currency": site_currency().lower(), "unit_amount": amount, "product_data": {"name": description[:250], **({"tax_code": self._tax_code} if self._tax_code else {})}},
                }
            ],
            "success_url": return_url,
            "cancel_url": return_url + ("&" if "?" in return_url else "?") + "cancelled=1",  # the page then says "you cancelled", not "not confirmed yet"
            "metadata": {"payment_reference": reference},
            "payment_intent_data": {"metadata": {"payment_reference": reference}},
        }
        if not self._tax_code:
            # Stripe accounts with Managed Payments on by default refuse a line without a product tax code; the square handles its own tax.
            params["managed_payments"] = {"enabled": False}
        session = self._call(self._client.v1.checkout.sessions.create, params=params, options={"idempotency_key": "create-" + hashlib.sha256(reference.encode()).hexdigest()[:32]})
        return {"id": session.id, "redirectUrl": session.url}

    def get_payment(self, session_id: str) -> dict:
        session = self._call(self._client.v1.checkout.sessions.retrieve, session_id)
        if session.payment_status == "paid":
            state = "AUTHORIZED"
        elif session.status == "expired":
            state = "EXPIRED"
        else:
            state = "CREATED"
        return {"state": state}

    def capture(self, session_id: str, amount: int) -> dict:
        return {}  # Checkout has already taken the money

    def cancel(self, session_id: str) -> dict:
        """Open session: expire it. Already paid (the sync found the order no longer payable): give the money back."""
        session = self._call(self._client.v1.checkout.sessions.retrieve, session_id)
        if session.payment_status == "paid":
            return self.refund(session_id, session.amount_total or 0)
        if session.status == "open":
            self._call(self._client.v1.checkout.sessions.expire, session_id)
        return {}

    def abandon(self, session_id: str) -> None:
        """The customer pressed back on the Stripe page: close the session if nothing was paid. Never refunds."""
        session = self._call(self._client.v1.checkout.sessions.retrieve, session_id)
        if session.status == "open" and session.payment_status != "paid":
            self._call(self._client.v1.checkout.sessions.expire, session_id)

    def refund(self, session_id: str, amount: int) -> dict:
        session = self._call(self._client.v1.checkout.sessions.retrieve, session_id)
        intent = session.payment_intent if isinstance(session.payment_intent, str) else getattr(session.payment_intent, "id", None)
        if not intent:
            raise StripeError("This Stripe payment has nothing to refund")
        refund = self._call(
            self._client.v1.refunds.create,
            params={"payment_intent": intent, "amount": amount},
            options={"idempotency_key": f"refund-{session_id}-{amount}"},
        )
        return {"id": refund.id}

    def register_webhook(self, url: str, events: list[str]) -> dict:
        endpoint = self._call(self._client.v1.webhook_endpoints.create, params={"url": url, "enabled_events": events})
        return {"id": endpoint.id, "secret": endpoint.secret}


def verify_webhook(payload: bytes, signature_header: str, secret: str):
    """The event, or None when the signature does not match this square's own signing secret."""
    if not secret or not signature_header:
        return None
    try:
        return stripe.Webhook.construct_event(payload, signature_header, secret)
    except (ValueError, stripe.SignatureVerificationError):
        return None

