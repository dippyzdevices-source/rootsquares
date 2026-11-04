"""Vipps MobilePay ePayment API integration (membership payments, "Pay in the Vipps app").

Separate from the manual Vipps QR flow (`provider="vipps_qr"`, admin-confirmed): this one is
`provider="vipps_app"` and is confirmed by Vipps itself. A payment goes
pending -> "initiated" (customer is at Vipps) -> "paid" | "failed" | "cancelled".

Money is integer øre throughout. `Payment.amount` is what the customer is charged (base fees +
`surcharge_amount`); the `PaymentAllocation` rows still sum to the base fees.

Nothing here trusts a webhook body or the browser's return: `sync_vipps_payment()` always asks
Vipps for the payment's real state and is idempotent, so the webhook and the return-page refresh
can both call it, in any order, any number of times.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import threading
import time
from datetime import datetime, timezone

import requests

from app.extensions import db
from app.payments import credentials
from app.payments.errors import GatewayError
from app.memberships.models import MembershipPeriod
from app.payments.fees import convenience_fee_for, convenience_percent, snapshot_processing_fee
from app.payments.models import Payment, PaymentAllocation

logger = logging.getLogger(__name__)

PROVIDER = "vipps_app"
ONLINE_PROVIDERS = ("vipps_app", "stripe")  # providers that confirm a payment themselves and share the sync below
TIMEOUT = 15
FINAL_STATUSES = {"paid", "failed", "cancelled", "refunded", "partially_refunded"}


class VippsError(GatewayError):
    """A Vipps API call failed (network error or non-2xx response). `status_code` is Vipps' answer when there was one."""


def is_public() -> bool:
    """Whether customers may choose "Vipps App" — credentials present AND the admin switch
    (Settings -> Payments, `SiteSettings.vipps_app_public`) on.
    (`is_enabled()` alone is enough for the admin-only test payment.)"""
    from app.settings.models import get_site_settings

    from app.common.site import site_currency

    # Vipps takes NOK only (rootsquares W6-R47): a square in another currency cannot offer Vipps App
    return is_enabled() and site_currency() == "NOK" and bool(get_site_settings().vipps_app_public)


def is_enabled() -> bool:
    """Whether THIS square has connected its own Vipps account (Settings -> Payments). There is no server-wide fallback."""
    return credentials.get_vipps() is not None


class VippsClient:
    _tokens: dict[tuple, tuple[str, float]] = {}  # one token per merchant (client id + serial number + environment), valid 24 h
    _lock = threading.Lock()

    def __init__(self, creds: "credentials.VippsCredentials | None" = None):
        creds = creds or credentials.get_vipps()
        if creds is None:
            raise VippsError("Vipps is not connected for this square")
        self.client_id = creds.client_id
        self.client_secret = creds.client_secret
        self.sub_key = creds.subscription_key
        self.msn = creds.msn
        self.base_url = "https://api.vipps.no" if creds.mode == "production" else "https://apitest.vipps.no"

    # -- auth (token cached per process; valid 24h) --------------------------------------
    def _access_token(self) -> str:
        cache_key = (self.base_url, self.client_id, self.msn)
        with VippsClient._lock:
            cached = VippsClient._tokens.get(cache_key)
            if cached and time.time() < cached[1] - 60:
                return cached[0]
            try:
                res = requests.post(
                    f"{self.base_url}/accesstoken/get",
                    headers={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "Ocp-Apim-Subscription-Key": self.sub_key,
                        "Merchant-Serial-Number": self.msn,
                    },
                    timeout=TIMEOUT,
                )
                res.raise_for_status()
                data = res.json()
            except requests.HTTPError as exc:
                raise VippsError("Vipps did not accept these keys", exc.response.status_code if exc.response is not None else None) from exc
            except (requests.RequestException, ValueError) as exc:
                raise VippsError("Could not get a Vipps access token") from exc
            VippsClient._tokens[cache_key] = (data["access_token"], float(data["expires_on"]))
            return data["access_token"]

    def _request(self, method: str, path: str, *, idempotency_key: str | None = None, json=None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Ocp-Apim-Subscription-Key": self.sub_key,
            "Merchant-Serial-Number": self.msn,
            "Vipps-System-Name": "rootsquares",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            res = requests.request(
                method, f"{self.base_url}{path}", headers=headers, json=json, timeout=TIMEOUT
            )
        except requests.RequestException as exc:
            raise VippsError(f"Vipps request failed: {method} {path}") from exc
        if not res.ok:
            logger.warning("Vipps %s %s -> %s %s", method, path, res.status_code, res.text[:300])
            raise VippsError(f"Vipps returned {res.status_code} for {method} {path}")
        try:
            return res.json() if res.content else {}
        except ValueError:
            return {}

    # -- ePayment API ---------------------------------------------------------------------
    def create_payment(self, reference: str, amount: int, return_url: str, description: str) -> dict:
        return self._request(
            "POST",
            "/epayment/v1/payments",
            idempotency_key=f"create-{reference}",
            json={
                "reference": reference,
                "amount": {"currency": "NOK", "value": amount},
                "paymentMethod": {"type": "WALLET"},
                "returnUrl": return_url,
                "userFlow": "WEB_REDIRECT",
                "paymentDescription": description[:100],
            },
        )

    def get_payment(self, reference: str) -> dict:
        return self._request("GET", f"/epayment/v1/payments/{reference}")

    def capture(self, reference: str, amount: int) -> dict:
        return self._request(
            "POST",
            f"/epayment/v1/payments/{reference}/capture",
            idempotency_key=f"capture-{reference}",
            json={"modificationAmount": {"currency": "NOK", "value": amount}},
        )

    def cancel(self, reference: str) -> dict:
        return self._request(
            "POST", f"/epayment/v1/payments/{reference}/cancel", idempotency_key=f"cancel-{reference}"
        )

    def refund(self, reference: str, amount: int) -> dict:
        return self._request(
            "POST",
            f"/epayment/v1/payments/{reference}/refund",
            idempotency_key=f"refund-{reference}",
            json={"modificationAmount": {"currency": "NOK", "value": amount}},
        )

    def register_webhook(self, url: str, events: list[str]) -> dict:
        return self._request("POST", "/webhooks/v1/webhooks", json={"url": url, "events": events})


def new_vipps_reference(payment: Payment) -> str:
    """8-50 chars [A-Za-z0-9-]. The random suffix keeps references unique even if a dev/test
    database is reset and `PAY-2026-000001` is issued again."""
    return f"{payment.payment_reference}-{secrets.token_hex(8)}"


def verify_webhook_signature(secret: str, method: str, path_and_query: str, headers, body: bytes) -> bool:
    """Vipps signs webhooks with HMAC-SHA256: the signed string is
    `METHOD
path?query
x-ms-date;host;x-ms-content-sha256`, and the body hash travels in
    `x-ms-content-sha256`. Both the signature and the body hash must check out."""
    if not secret:
        return False
    date = headers.get("x-ms-date", "")
    host = headers.get("host", "")
    content_hash = headers.get("x-ms-content-sha256", "")
    auth = headers.get("authorization", "")
    expected_hash = base64.b64encode(hashlib.sha256(body).digest()).decode()
    if not date or not host or not hmac.compare_digest(content_hash, expected_hash):
        return False
    to_sign = f"{method}\n{path_and_query}\n{date};{host};{content_hash}"
    signature = base64.b64encode(
        hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).digest()
    ).decode()
    expected_auth = (
        f"HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256&Signature={signature}"
    )
    return hmac.compare_digest(auth, expected_auth)


def client_for(provider: str):
    """The client of an online provider. Stripe's answers in the Vipps words used below (AUTHORIZED = paid, EXPIRED, CREATED = still open)."""
    if provider == PROVIDER:
        return VippsClient()
    from app.payments import stripe_gateway

    return stripe_gateway.StripeClient()


def sync_vipps_payment(payment: Payment) -> Payment:
    """Bring `payment` in line with what its provider (Vipps or Stripe) says. Idempotent; safe to call from the webhook
    and from the return-page refresh at the same time (the row is locked while it runs)."""
    if payment.provider not in ONLINE_PROVIDERS or not payment.provider_transaction_id:
        return payment

    locked = (
        db.session.query(Payment).filter(Payment.id == payment.id).with_for_update().one()
    )
    if locked.status in FINAL_STATUSES:
        return locked

    client = client_for(locked.provider)
    reference = locked.provider_transaction_id
    state = client.get_payment(reference).get("state")

    if locked.payment_type == "event_ticket":
        return _sync_ticket_payment(locked, client, reference, state)
    if locked.payment_type == "event_donation":
        return _sync_event_donation_payment(locked, client, reference, state)
    if locked.payment_type == "donation":
        return _sync_donation_payment(locked, client, reference, state)

    allocations = PaymentAllocation.query.filter_by(payment_id=locked.id).all()
    periods = [db.session.get(MembershipPeriod, a.membership_period_id) for a in allocations]
    periods = [p for p in periods if p is not None]

    if state == "AUTHORIZED":
        if any(p.status != "unpaid" for p in periods):
            # Another payment already settled one of these periods — release this authorisation
            # (nothing has been charged yet) rather than take money twice.
            client.cancel(reference)
            locked.status = "cancelled"
        else:
            client.capture(reference, locked.amount)
            now = datetime.now(timezone.utc)
            locked.status = "paid"
            locked.paid_at = now
            snapshot_processing_fee(locked)
            for period in periods:
                period.status = "paid"
                period.paid_at = now
    elif state in ("ABORTED", "EXPIRED", "TERMINATED"):
        locked.status = "failed"
    # CREATED (customer hasn't finished yet) -> stay "initiated".

    db.session.commit()
    if locked.status == "paid":
        # Imported here: the memberships service imports the payments models, not this module,
        # but keeping it local avoids any import-order surprise at app start.
        from app.memberships.service import activate_pending_memberships_after_payment

        # A member's first payment on a self-service request activates that membership.
        activate_pending_memberships_after_payment(periods)
    return locked


def _sync_event_donation_payment(locked: Payment, client: "VippsClient", reference: str, state: str | None) -> Payment:
    """A donation made through the event page: on AUTHORIZED the money is captured and the
    contribution counts (status paid); an aborted/expired attempt marks it failed."""
    from app.accounting.models import EventContribution

    contribution = EventContribution.query.filter_by(payment_id=locked.id).first()
    if state == "AUTHORIZED":
        client.capture(reference, locked.amount)
        locked.status = "paid"
        locked.paid_at = datetime.now(timezone.utc)
        snapshot_processing_fee(locked)
        if contribution is not None:
            contribution.status = "paid"
    elif state in ("ABORTED", "EXPIRED", "TERMINATED"):
        locked.status = "failed"
        if contribution is not None:
            contribution.status = "failed"
    db.session.commit()
    return locked


def _sync_ticket_payment(locked: Payment, client: "VippsClient", reference: str, state: str | None) -> Payment:
    """Ticket-order counterpart of the membership branch above. On AUTHORIZED the order becomes
    paid/confirmed and its tickets are issued (the same `issue_tickets_for_order` the admin
    mark-paid uses) — unless the order is no longer payable (rejected/cancelled/already paid by
    an admin), in which case the authorisation is released instead."""
    # Imported here: app.orders.routes imports this module, so a top-level import would be circular.
    from app.coupons.models import Coupon
    from app.coupons.service import deactivate_coupon_if_limit_reached
    from app.orders.emails import send_tickets_confirmed_email, send_vipps_payment_failed_email
    from app.orders.models import Order
    from app.orders.service import issue_tickets_for_order

    order = (
        db.session.query(Order).filter(Order.id == locked.order_id).with_for_update().first()
        if locked.order_id
        else None
    )
    paid_order = None
    failed_order = None
    if state == "AUTHORIZED":
        if order is None or order.payment_status not in ("pending", "pending_verification"):
            client.cancel(reference)
            locked.status = "cancelled"
        else:
            client.capture(reference, locked.amount)
            locked.status = "paid"
            locked.paid_at = datetime.now(timezone.utc)
            snapshot_processing_fee(locked)
            order.payment_status = "paid"
            order.order_status = "confirmed"
            issue_tickets_for_order(order)
            paid_order = order
    elif state in ("ABORTED", "EXPIRED", "TERMINATED"):
        locked.status = "failed"
        # A failed Vipps checkout is not something for an admin to approve: cancel the order so its seats are
        # released and it stays out of the "needs action" queue. Only when nothing else is in play - an order
        # the customer has since claimed as paid (pending_verification), or one with another live or paid
        # payment, is left alone.
        if order is not None and order.payment_status == "pending":
            others = Payment.query.filter(
                Payment.order_id == order.id,
                Payment.id != locked.id,
                Payment.status.in_(("initiated", "paid")),
            ).count()
            if not others:
                order.payment_status = "failed"
                order.order_status = "cancelled"
                failed_order = order

    db.session.commit()

    if failed_order is not None:
        send_vipps_payment_failed_email(failed_order)
    if paid_order is not None:
        if paid_order.coupon_id:
            coupon = db.session.get(Coupon, paid_order.coupon_id)
            if coupon is not None:
                deactivate_coupon_if_limit_reached(coupon)
        send_tickets_confirmed_email(paid_order)
    return locked


def _sync_donation_payment(locked: Payment, client: "VippsClient", reference: str, state: str | None) -> Payment:
    """Donation counterpart of the ticket branch: on AUTHORIZED the gift is captured and marked paid (and the receipt sent); an abandoned
    attempt becomes failed. A donation an admin already settled or rejected releases the authorisation instead of taking money twice."""
    from app.donations.emails import send_donation_receipt_email
    from app.donations.models import Donation

    donation = (
        db.session.query(Donation).filter(Donation.id == locked.donation_id).with_for_update().first()
        if locked.donation_id
        else None
    )
    paid_donation = None
    if state == "AUTHORIZED":
        if donation is None or donation.status not in ("pending", "pending_verification"):
            client.cancel(reference)
            locked.status = "cancelled"
        else:
            client.capture(reference, locked.amount)
            now = datetime.now(timezone.utc)
            locked.status = "paid"
            locked.paid_at = now
            donation.status = "paid"
            donation.paid_at = now
            paid_donation = donation
    elif state in ("ABORTED", "EXPIRED", "TERMINATED"):
        locked.status = "failed"
        if donation is not None and donation.status in ("pending", "pending_verification"):
            donation.status = "cancelled"

    db.session.commit()
    if paid_donation is not None:
        send_donation_receipt_email(paid_donation)
    return locked


def sweep_initiated_payments(limit: int = 50) -> int:
    """Safety net behind the webhook: re-check Vipps payments still "initiated" (the customer
    paid and never came back, or the webhook never arrived). Skips ones created in the last
    minute — the customer is probably still at Vipps and the redirect will handle it — and
    returns how many were looked at. Each one is isolated, so a single failure never blocks
    the rest."""
    from datetime import timedelta

    from app.payments import stripe_gateway

    if not (is_enabled() or stripe_gateway.is_enabled()):  # this square has no online provider connected: nothing to check
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    stale = (
        Payment.query.filter(
            Payment.provider.in_(ONLINE_PROVIDERS),
            Payment.status == "initiated",
            Payment.created_at < cutoff,
        )
        .order_by(Payment.created_at)
        .limit(limit)
        .all()
    )
    checked = 0
    for payment in stale:
        try:
            sync_vipps_payment(payment)
            checked += 1
        except GatewayError:
            db.session.rollback()
            logger.warning("Payment sweep: could not check payment %s", payment.id)
        except Exception:  # noqa: BLE001 - one bad payment must not stop the sweep
            db.session.rollback()
            logger.exception("Vipps sweep: unexpected error on payment %s", payment.id)
    return checked
