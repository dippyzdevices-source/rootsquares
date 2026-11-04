"""Platform billing, prepared (rootsquares W10-R42, docs/plans/pricing-strategy.md, ADR 043, docs/setup/22-stripe-billing.md).

What exists now: prices as data (`plan_prices`), billing orders (`billing_orders`), a provider interface with a FAKE provider (a test checkout page, no money
moves) and the Stripe adapter (W12-R4), the rules for an upgrade (pay the difference) and for a running period, and the one
function that applies a paid order (idempotent). What the user adds later: the Stripe adapter (`StripeBillingProvider`), the keys and the webhook (the guide
lists the steps).

Money is integer minor units plus a currency (USD only). No card data ever reaches this code or database; the provider's page takes it.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

import stripe
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import event_pass, plans
from app.platform.models import AuditLog, BillingOrder, PlanPrice, Square
from app.shared.config import Settings
from app.shared.errors import AppError, BadRequestError, ConflictError

log = structlog.get_logger("app.billing")
CURRENCY = "USD"
# The Stripe events the webhook endpoint must be subscribed to (docs/setup/24-stripe-setup-and-commands.md). Everything else is acknowledged and ignored.
WEBHOOK_EVENTS = (
    "checkout.session.completed",
    "checkout.session.expired",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.deleted",
)

# The prices the platform has, and how each is paid. **No amount is in the code** (W14-R29): the amounts are rows of `plan_prices`, set by a platform
# admin on the owner console Prices page (or `PUT /prices/<key>`). A price that has not been set cannot be charged: the checkout says so.
PRICE_KEYS: dict[str, str] = {
    "launch.roots": "one_off",
    "launch.square": "one_off",
    "launch.grove": "one_off",
    "launch.event": "one_off",  # the Event pass
    "running.keep.month": "month",
    "running.keep.year": "year",
    "running.live.month": "month",
    "running.live.year": "year",
}
UPGRADE_ORDER = (plans.ROOTS, plans.SQUARE, plans.GROVE)  # the event pass is not part of the ladder


class BillingNotReady(AppError):
    status, code, title = 501, "billing_not_ready", "Billing is not ready"


class PaymentRequired(AppError):
    status, code, title = 402, "payment_required", "Payment required"


class PriceNotSet(AppError):
    status, code, title = 409, "price_not_set", "A price is not set"


class PlanChangeDeclined(AppError):
    status, code, title = 402, "plan_change_declined", "The payment did not go through"


def list_prices(db: Session) -> list[PlanPrice]:
    """The prices that are set, in the order of PRICE_KEYS (others after). Nothing is created: an empty table means no price is set yet."""
    have = {p.key: p for p in db.scalars(select(PlanPrice))}
    return [have[k] for k in PRICE_KEYS if k in have] + [p for k, p in have.items() if k not in PRICE_KEYS]


def set_price(db: Session, key: str, amount_minor: int) -> PlanPrice:
    """Set or change a price (a platform admin). A key that is not in PRICE_KEYS is refused by the caller."""
    row = db.get(PlanPrice, key)
    if row is None:
        row = PlanPrice(key=key, amount_minor=amount_minor, currency=CURRENCY, interval=PRICE_KEYS[key])
        db.add(row)
    else:
        row.amount_minor = amount_minor
    db.flush()
    return row


def price_or_none(db: Session, key: str) -> int | None:
    row = db.get(PlanPrice, key)
    return row.amount_minor if row is not None else None


def price_of(db: Session, key: str) -> int:
    amount = price_or_none(db, key)
    if amount is None:
        raise PriceNotSet(f"The price {key} is not set. A platform admin sets it on the Prices page of the owner console.")
    return amount


def upgrade_amount(db: Session, current: str | None, target: str) -> int:
    """The difference to pay to move up the ladder; 0 or less is refused by the caller (nothing to upgrade, or a step down)."""
    here = current or plans.LEGACY_PACKAGE
    if here not in UPGRADE_ORDER or target not in UPGRADE_ORDER or UPGRADE_ORDER.index(target) <= UPGRADE_ORDER.index(here):
        return 0
    return price_of(db, f"launch.{target}") - price_of(db, f"launch.{here}")


# ---- providers ------------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Checkout:
    url: str  # where the browser goes to pay
    ref: str  # the provider's id of the checkout, kept on the order


@dataclass(frozen=True)
class PlanChange:
    """What the provider did when the price of a subscription was changed (W18-R34)."""

    paid: bool = True  # False = an immediate change that was not paid (the provider changed nothing)
    amount_minor: int = 0  # what was charged now (0 for a change that starts at the next renewal)
    invoice_id: str | None = None  # the invoice of an immediate change, kept on the order


@dataclass(frozen=True)
class PaymentEvent:
    order_id: uuid.UUID | None = None  # the order paid or failed; for a renewal, the order that started the subscription
    paid: bool = True  # True = paid, False = cancelled or failed
    subscription_id: str | None = None  # the provider's renewing subscription, when there is one (W12-R13)
    invoice_id: str | None = None  # set for a renewal: the provider's invoice of the new period (kept on the order, so a replay is ignored)
    amount_minor: int | None = None  # a renewal: what was paid
    ended: bool = False  # the subscription is over (cancelled and its time is up)
    failed: bool = False  # a renewal payment failed (the card was refused); the provider retries for a while (W12-R18)
    card_brand: str | None = None  # from the provider, for the history (W12-R8)
    card_last4: str | None = None


def tax_rates(settings: Settings) -> dict[str, float]:
    """`BILLING_TAX_RATES` ("NO:25,SE:25") as {country: percent}; a malformed pair is skipped."""
    rates: dict[str, float] = {}
    for part in (settings.BILLING_TAX_RATES or "").split(","):
        country, _, pct = part.strip().partition(":")
        try:
            value = float(pct)
        except ValueError:
            continue
        if len(country.strip()) == 2 and 0 < value < 100:
            rates[country.strip().upper()] = value
    return rates


def tax_percent(settings: Settings, country: str | None) -> float:
    """The tax percent already inside the listed price for a billing country, or 0 (the listed price is sent as it is)."""
    return tax_rates(settings).get((country or "").upper(), 0.0)


def net_minor(gross_minor: int, percent: float) -> int:
    """The amount to send Stripe so that, with `percent` tax added on top, the customer pays `gross_minor` in all (rounded to the cent)."""
    if percent <= 0:
        return gross_minor
    return int((Decimal(gross_minor) * 100 / (100 + Decimal(str(percent)))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def tax_split(gross_minor: int, percent: float) -> tuple[int, int]:
    """(amount without tax, tax) of a price that includes `percent` tax."""
    net = net_minor(gross_minor, percent)
    return net, gross_minor - net


class BillingProvider(Protocol):
    name: str

    def ensure_customer(self, existing: str | None, name: str, email: str, country: str | None) -> str | None:
        """The provider's customer for an organisation (made once, kept on the organisation), or None when the provider has no such thing."""
        ...

    def create_checkout(
        self, order: BillingOrder, success_url: str, cancel_url: str, launch_minor: int = 0, customer: str | None = None, tax_percent: float = 0.0
    ) -> Checkout: ...

    def create_portal(self, customer: str, return_url: str) -> str | None:
        """The provider's page where the customer changes the card and downloads receipts, or None when there is none."""
        ...

    def check_checkout(self, order: BillingOrder) -> PaymentEvent | None:
        """Ask the provider what became of the order's checkout (W25-R27): a paid or expired answer in the same shape as a webhook,
        or None while it is still open. The safety net for a webhook that never came; the webhook stays the main route."""
        ...

    def refund(self, order: BillingOrder, amount_minor: int | None = None) -> None:
        """Give a payment of an order back to the customer (money moves): all of it (including tax) when `amount_minor` is empty, else that amount.
        Safe to repeat: the provider is told it is the same refund."""
        ...

    def end_subscription(self, subscription_id: str) -> None:
        """End a renewing subscription at once (after a refund)."""
        ...

    def set_renewal(self, subscription_id: str, renew: bool) -> None:
        """Stop (or resume) the automatic renewal: the paid time stays, nothing is refunded."""
        ...

    def change_plan(
        self, subscription_id: str, plan: str, interval: str, amount_minor: int, tax_percent: float, immediate: bool, charge_minor: int = 0
    ) -> PlanChange:
        """Put another price on the renewing subscription (W18-R34). `immediate`: charge the rest of the period now and fail without a payment;
        otherwise the paid period is left alone and the next renewal is at the new price. `amount_minor` is the listed price, tax included."""
        ...

    def read_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent | None:
        """Verify the provider's signature and say which order was paid or failed; None for an event we do not care about. Raise on a bad signature."""


class FakeBillingProvider:
    """A test checkout inside the platform frontend (`/billing/checkout?order=...`): the page asks to pay or cancel and the platform confirms by itself.
    Used in local and test; refused in production (Settings)."""

    name = "fake"

    def __init__(self, frontend_url: str) -> None:
        self._frontend = frontend_url.rstrip("/")

    def ensure_customer(self, existing: str | None, name: str, email: str, country: str | None) -> str | None:
        return existing

    def create_checkout(
        self, order: BillingOrder, success_url: str, cancel_url: str, launch_minor: int = 0, customer: str | None = None, tax_percent: float = 0.0
    ) -> Checkout:
        return Checkout(url=f"{self._frontend}/billing/checkout?order={order.id}", ref=f"fake_{order.id}")

    def create_portal(self, customer: str, return_url: str) -> str | None:
        return None

    def check_checkout(self, order: BillingOrder) -> PaymentEvent | None:
        return None  # the fake checkout page pays or cancels at once, there is nothing to ask

    def refund(self, order: BillingOrder, amount_minor: int | None = None) -> None:
        return None  # nothing moved: the fake checkout took no money

    def end_subscription(self, subscription_id: str) -> None:
        return None

    def set_renewal(self, subscription_id: str, renew: bool) -> None:
        return None

    def change_plan(
        self, subscription_id: str, plan: str, interval: str, amount_minor: int, tax_percent: float, immediate: bool, charge_minor: int = 0
    ) -> PlanChange:
        """The fake keeps no subscription: an immediate change is charged what the platform worked out (`charge_minor`), a later one is free now."""
        return PlanChange(paid=True, amount_minor=charge_minor if immediate else 0, invoice_id=f"fake_inv_{subscription_id}_{plan}" if immediate else None)

    def read_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent | None:
        raise BillingNotReady("The fake provider has no webhook; use the test checkout page")


class StripeBillingProvider:
    """Stripe Checkout (W12-R4, docs/setup/22-stripe-billing.md section 5). `create_checkout` makes a Checkout Session with dynamic USD `price_data` from the
    order (mode payment for an upgrade or an Event pass upgrade, mode subscription for a running plan) and the order id in the metadata; `read_webhook`
    checks the Stripe-Signature header with STRIPE_WEBHOOK_SECRET and turns a paid or expired session into a PaymentEvent. Nothing here prints or logs a key."""

    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str, tax_code: str = "", test_clock: str = "") -> None:
        self._test_clock = test_clock
        self._secret = secret_key
        self._webhook_secret = webhook_secret
        self._tax_code = tax_code

    def _client(self) -> stripe.StripeClient:
        return stripe.StripeClient(self._secret)

    @staticmethod
    def _product_name(order: BillingOrder) -> str:
        if order.kind in ("running", "first"):
            return f"rootsquares {(order.running_plan or '').title()} ({'yearly' if order.interval == 'year' else 'monthly'})"
        if order.kind == "event_upgrade":
            return f"rootsquares {(order.launch_package or '').title()} package and first Live period"
        return f"rootsquares upgrade to {(order.launch_package or '').title()}"

    def _card_of(self, session_id: str) -> tuple[str | None, str | None]:
        """The brand and last four digits of the card that paid (best effort: a failed lookup never blocks the payment)."""
        if not session_id:
            return None, None
        try:
            ses = self._client().v1.checkout.sessions.retrieve(
                session_id, params={"expand": ["payment_intent.payment_method", "subscription.default_payment_method"]}
            )
            data = ses.to_dict()
            pi, sub = data.get("payment_intent"), data.get("subscription")
            pm = (pi or {}).get("payment_method") if pi else (sub or {}).get("default_payment_method") if sub else None
            card = (pm or {}).get("card") or {}
            return card.get("brand"), card.get("last4")
        except Exception as exc:  # noqa: BLE001 - the card is a nicety; log the type only
            log.warning("stripe_card_lookup_failed", error=type(exc).__name__)
            return None, None

    def check_checkout(self, order: BillingOrder) -> PaymentEvent | None:
        """Ask Stripe what became of the order's Checkout Session and answer in the shape of a webhook (W25-R27). Only a session that carries this order's id
        counts. A failed lookup is logged by type and answers None: the order simply stays pending."""
        ref = order.provider_ref or ""
        if not ref.startswith("cs_"):
            return None
        try:
            data = self._client().v1.checkout.sessions.retrieve(ref).to_dict()
        except stripe.StripeError as exc:
            log.warning("stripe_session_lookup_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None))
            return None
        if str((data.get("metadata") or {}).get("order_id") or data.get("client_reference_id") or "") != str(order.id):
            return None
        if data.get("payment_status") in ("paid", "no_payment_required"):
            brand, last4 = self._card_of(ref)
            sub = data.get("subscription")
            return PaymentEvent(order_id=order.id, paid=True, card_brand=brand, card_last4=last4, subscription_id=str(sub) if sub else None)
        if data.get("status") == "expired":
            return PaymentEvent(order_id=order.id, paid=False)
        return None

    def ensure_customer(self, existing: str | None, name: str, email: str, country: str | None) -> str | None:
        """One Stripe customer per organisation, with the country the owner gave, so the checkout starts with it and tax is worked out from it."""
        if existing:
            if country:  # the owner's country may have been set after the customer was made: keep Stripe's copy equal
                try:
                    self._client().v1.customers.update(existing, params={"address": {"country": country}})
                except stripe.StripeError as exc:
                    log.warning("stripe_customer_update_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None))
            return existing
        try:
            params: dict[str, Any] = {"name": name, "email": email, **({"address": {"country": country}} if country else {})}
            if self._test_clock:
                params["test_clock"] = self._test_clock  # test mode: lets a test clock move this customer's time
            made = self._client().v1.customers.create(params=params)  # type: ignore[arg-type]
        except stripe.StripeError as exc:
            log.warning("stripe_customer_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None))
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc
        return made.id

    def create_checkout(
        self, order: BillingOrder, success_url: str, cancel_url: str, launch_minor: int = 0, customer: str | None = None, tax_percent: float = 0.0
    ) -> Checkout:
        """`launch_minor`: for a `first` order, the part of the amount that is the launch package (a one-time line next to the recurring period)."""
        meta = {"order_id": str(order.id)}
        price_data: dict[str, Any] = {
            "currency": order.currency.lower(),
            "unit_amount": net_minor(order.amount_minor, tax_percent),  # the listed price includes the tax that Stripe adds (W13-R51)
            "product_data": {"name": self._product_name(order), **({"tax_code": self._tax_code} if self._tax_code else {})},
        }
        params: dict[str, Any] = {
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(order.id),
            "billing_address_collection": "required",  # tax is worked out from the address, so ask for it up front
            "metadata": meta,
        }
        if customer:
            params.update(customer=customer, customer_update={"address": "auto", "name": "auto"})  # keep the address the buyer types
        lines = [{"price_data": price_data, "quantity": 1}]
        if order.kind in ("running", "first"):
            if order.kind == "first" and 0 < launch_minor < order.amount_minor:
                # the launch package (once) and the first running period (renewing) in one checkout
                price_data["unit_amount"] = net_minor(order.amount_minor - launch_minor, tax_percent)
                once = {
                    "currency": price_data["currency"],
                    "unit_amount": net_minor(launch_minor, tax_percent),
                    "product_data": {**price_data["product_data"], "name": f"rootsquares {(order.launch_package or '').title()} launch package"},
                }
                lines.append({"price_data": once, "quantity": 1})
            price_data["recurring"] = {"interval": "year" if order.interval == "year" else "month"}
            params.update(mode="subscription", subscription_data={"metadata": meta})
        else:
            params.update(mode="payment", payment_intent_data={"metadata": meta})
        params["line_items"] = lines
        try:
            session = self._client().v1.checkout.sessions.create(params=params)  # type: ignore[arg-type]
        except stripe.StripeError as exc:
            log.warning("stripe_checkout_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None), stripe_code=getattr(exc, "code", None))
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc  # the error type only, never its text
        if not session.url:
            raise AppError("The payment provider gave no checkout address", code="provider_error")
        return Checkout(url=session.url, ref=session.id)

    def create_portal(self, customer: str, return_url: str) -> str | None:
        try:
            session = self._client().v1.billing_portal.sessions.create(params={"customer": customer, "return_url": return_url})
        except stripe.StripeError as exc:
            log.warning("stripe_portal_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None), stripe_code=getattr(exc, "code", None))
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc
        return str(session.url)

    def _payment_intent_of_invoice(self, invoice_id: str) -> str | None:
        """The payment of a renewal: its order keeps the invoice id (a first payment keeps the checkout session id)."""
        inv = self._client().v1.invoices.retrieve(invoice_id).to_dict()
        direct = inv.get("payment_intent")
        if direct:
            return str(direct.get("id") if isinstance(direct, dict) else direct)
        pays = self._client().v1.invoice_payments.list(params={"invoice": invoice_id, "limit": 1}).to_dict().get("data") or []
        found = ((pays[0].get("payment") or {}).get("payment_intent")) if pays else None
        return str(found) if found else None

    def _payment_intent_of(self, session_id: str) -> str | None:
        if session_id.startswith("in_"):
            return self._payment_intent_of_invoice(session_id)
        ses = self._client().v1.checkout.sessions.retrieve(session_id, params={"expand": ["payment_intent", "invoice"]}).to_dict()
        pi = ses.get("payment_intent")
        if pi:
            return str(pi.get("id") if isinstance(pi, dict) else pi)
        inv = ses.get("invoice")
        if isinstance(inv, dict):
            direct = inv.get("payment_intent")
            if direct:
                return str(direct.get("id") if isinstance(direct, dict) else direct)
            if inv.get("id"):  # newer API versions: the payments of an invoice
                pays = self._client().v1.invoice_payments.list(params={"invoice": inv["id"], "limit": 1}).to_dict().get("data") or []
                found = ((pays[0].get("payment") or {}).get("payment_intent")) if pays else None
                if found:
                    return str(found)
        return None

    def refund(self, order: BillingOrder, amount_minor: int | None = None) -> None:
        try:
            pi = self._payment_intent_of(order.provider_ref or "")
            if pi is None:
                raise AppError("The payment to refund was not found at the provider", code="refund_failed")
            params: dict[str, Any] = {"payment_intent": pi, "metadata": {"order_id": str(order.id)}}
            key = f"refund-{order.id}"  # the whole payment: one refund per order
            if amount_minor is not None:
                params["amount"] = amount_minor
                key = f"{key}-{getattr(order, 'refunded_minor', 0)}-{amount_minor}"  # a repeat of the same partial refund is the same refund
            self._client().v1.refunds.create(params=params, options={"idempotency_key": key})  # type: ignore[arg-type]
        except stripe.StripeError as exc:
            log.warning("stripe_refund_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None), stripe_code=getattr(exc, "code", None))
            raise AppError("The payment provider did not accept the refund", code="refund_failed") from exc

    def end_subscription(self, subscription_id: str) -> None:
        try:
            self._client().v1.subscriptions.cancel(subscription_id)
        except stripe.StripeError as exc:
            log.warning("stripe_end_subscription_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None))
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc

    def set_renewal(self, subscription_id: str, renew: bool) -> None:
        try:
            self._client().v1.subscriptions.update(subscription_id, params={"cancel_at_period_end": not renew})
        except stripe.StripeError as exc:
            log.warning("stripe_renewal_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None))
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc

    def change_plan(
        self, subscription_id: str, plan: str, interval: str, amount_minor: int, tax_percent: float, immediate: bool, charge_minor: int = 0
    ) -> PlanChange:
        """Swap the price of the one subscription (never a second one). A subscription update needs a product id, so a product named for the plan is made here
        (a change of plan is rare). Later: proration off, the paid period is untouched and the next renewal is at the new price. Now: the proration is invoiced
        at once and the update fails when the card does not pay, so nothing is changed without money."""
        client = self._client()
        try:
            sub = client.v1.subscriptions.retrieve(subscription_id).to_dict()
            item_id = ((sub.get("items") or {}).get("data") or [{}])[0].get("id")
            if not item_id:
                raise AppError("The payment provider has no subscription item", code="provider_error")
            label = "yearly" if interval == "year" else "monthly"
            product_params: dict[str, Any] = {"name": f"rootsquares {plan.title()} ({label})"}
            if self._tax_code:
                product_params["tax_code"] = self._tax_code
            product = client.v1.products.create(params=product_params)  # type: ignore[arg-type]
            params: dict[str, Any] = {
                "items": [
                    {
                        "id": item_id,
                        "price_data": {
                            "currency": CURRENCY.lower(),
                            "product": product.id,
                            "unit_amount": net_minor(amount_minor, tax_percent),  # the listed price includes the tax Stripe adds (W13-R51)
                            "recurring": {"interval": "year" if interval == "year" else "month"},
                        },
                    }
                ],
                "proration_behavior": "always_invoice" if immediate else "none",
            }
            if immediate:
                params.update(payment_behavior="error_if_incomplete", expand=["latest_invoice"])
            updated = client.v1.subscriptions.update(subscription_id, params=params).to_dict()  # type: ignore[arg-type]
        except stripe.StripeError as exc:
            log.warning("stripe_change_plan_failed", error=type(exc).__name__, status=getattr(exc, "http_status", None), stripe_code=getattr(exc, "code", None))
            if immediate and isinstance(exc, stripe.CardError | stripe.InvalidRequestError):
                raise PlanChangeDeclined("The payment did not go through, so the plan has not changed") from exc
            raise AppError("The payment provider did not accept the request", code="provider_error") from exc
        if not immediate:
            return PlanChange(paid=True, amount_minor=0)
        inv = updated.get("latest_invoice") or {}
        if not isinstance(inv, dict) or inv.get("status") != "paid":
            raise PlanChangeDeclined("The payment did not go through, so the plan has not changed")
        return PlanChange(paid=True, amount_minor=int(inv.get("amount_paid") or 0), invoice_id=str(inv.get("id")))

    def _renewal_of(self, obj: dict[str, Any], failed: bool = False) -> PaymentEvent | None:
        """A paid (or, with `failed`, refused) invoice of a later period of a subscription (the first one is handled by the checkout itself)."""
        if obj.get("billing_reason") != "subscription_cycle":
            return None
        details = obj.get("subscription_details") or (obj.get("parent") or {}).get("subscription_details") or {}
        sub_id = obj.get("subscription") or details.get("subscription")
        meta = details.get("metadata") or {}
        if sub_id and not meta.get("order_id"):
            try:
                meta = self._client().v1.subscriptions.retrieve(str(sub_id)).to_dict().get("metadata") or {}
            except stripe.StripeError:
                return None
        try:
            oid = uuid.UUID(str(meta.get("order_id")))
        except ValueError:
            return None
        if failed:
            return PaymentEvent(order_id=oid, paid=False, failed=True, subscription_id=str(sub_id) if sub_id else None, invoice_id=str(obj.get("id")))
        brand, last4 = self._card_of_subscription(str(sub_id)) if sub_id else (None, None)
        return PaymentEvent(
            order_id=oid,
            paid=True,
            subscription_id=str(sub_id) if sub_id else None,
            invoice_id=str(obj.get("id")),
            amount_minor=int(obj.get("amount_paid") or 0),
            card_brand=brand,
            card_last4=last4,
        )

    def _card_of_subscription(self, sub_id: str) -> tuple[str | None, str | None]:
        try:
            sub = self._client().v1.subscriptions.retrieve(sub_id, params={"expand": ["default_payment_method"]}).to_dict()
            card = (sub.get("default_payment_method") or {}).get("card") or {}
            return card.get("brand"), card.get("last4")
        except Exception as exc:  # noqa: BLE001 - the card is a nicety
            log.warning("stripe_card_lookup_failed", error=type(exc).__name__)
            return None, None

    def read_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent | None:
        signature = next((v for k, v in headers.items() if k.lower() == "stripe-signature"), "")
        try:
            event = stripe.Webhook.construct_event(body, signature, self._webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise BadRequestError("Bad webhook signature", code="bad_signature") from exc
        obj = event["data"]["object"].to_dict()
        if event["type"] == "invoice.paid":
            return self._renewal_of(obj)
        if event["type"] == "invoice.payment_failed":
            return self._renewal_of(obj, failed=True)
        if event["type"] == "customer.subscription.deleted":
            return PaymentEvent(subscription_id=str(obj.get("id")), ended=True)
        order_id = (obj.get("metadata") or {}).get("order_id") or obj.get("client_reference_id")
        if event["type"] not in ("checkout.session.completed", "checkout.session.expired") or not order_id:
            # payment_intent.payment_failed is ignored on purpose:
            # Checkout lets the customer try another card in the same session, and a cancelled order could not be paid afterwards.
            return None
        try:
            oid = uuid.UUID(str(order_id))
        except ValueError:
            return None
        if event["type"] == "checkout.session.expired":
            return PaymentEvent(order_id=oid, paid=False)
        if obj.get("payment_status") in ("paid", "no_payment_required"):
            brand, last4 = self._card_of(str(obj.get("id") or ""))
            sub = obj.get("subscription")
            return PaymentEvent(order_id=oid, paid=True, card_brand=brand, card_last4=last4, subscription_id=str(sub) if sub else None)
        return None  # completed but not yet paid (a delayed payment method): wait for the later event


def build_billing(settings: Settings) -> BillingProvider:
    if settings.BILLING_PROVIDER == "stripe":
        return StripeBillingProvider(settings.STRIPE_SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET, settings.STRIPE_TAX_CODE, settings.STRIPE_TEST_CLOCK_ID)
    return FakeBillingProvider(settings.PLATFORM_FRONTEND_URL)


# ---- orders ---------------------------------------------------------------------------------------------------------------------------


def new_upgrade_order(db: Session, sq: Square, target: str, user_id: uuid.UUID | None, provider: str) -> BillingOrder:
    amount = upgrade_amount(db, sq.launch_package, target)
    if amount <= 0:
        raise ConflictError("There is nothing to upgrade to", code="no_upgrade")
    order = BillingOrder(square_id=sq.id, created_by=user_id, kind="upgrade", launch_package=target, amount_minor=amount, currency=CURRENCY, provider=provider)
    db.add(order)
    db.flush()
    return order


def event_upgrade_amount(db: Session, target: str, interval: str) -> int:
    """An Event pass becoming a launch package plus Live: the package price minus the Event pass price already paid, plus the first Live period."""
    if target not in UPGRADE_ORDER or interval not in ("month", "year"):
        raise BadRequestError("Choose a launch package and a monthly or yearly period", code="bad_plan")
    return max(0, price_of(db, f"launch.{target}") - price_of(db, f"launch.{plans.EVENT}")) + price_of(db, f"running.{plans.LIVE}.{interval}")


def new_event_upgrade_order(db: Session, sq: Square, target: str, interval: str, user_id: uuid.UUID | None, provider: str) -> BillingOrder:
    if not event_pass.is_event_pass(sq) or event_pass.phase(sq) == event_pass.REMOVED:
        raise ConflictError("Only a running Event pass can be upgraded", code="not_event_pass")
    order = BillingOrder(
        square_id=sq.id, created_by=user_id, kind="event_upgrade", launch_package=target, running_plan=plans.LIVE, interval=interval,
        amount_minor=event_upgrade_amount(db, target, interval), currency=CURRENCY, provider=provider,
    )  # fmt: skip
    db.add(order)
    db.flush()
    return order


def payment_before_build(settings: Settings) -> bool:
    return settings.BILLING_PROVIDER == "stripe" or settings.BILLING_ENFORCE


def event_pass_payment_required(settings: Settings) -> bool:
    """A new Event pass is paid before it is built with Stripe or BILLING_ENFORCE; with the fake provider it starts at once (local, test)."""
    return settings.BILLING_PROVIDER == "stripe" or settings.BILLING_ENFORCE


def new_event_pass_order(db: Session, sq: Square, user_id: uuid.UUID | None, provider: str) -> BillingOrder:
    if not event_pass.awaiting_payment(sq):
        raise ConflictError("This Event pass is already paid", code="not_awaiting_payment")
    order = BillingOrder(
        square_id=sq.id, created_by=user_id, kind="event_pass", launch_package=plans.EVENT, amount_minor=price_of(db, f"launch.{plans.EVENT}"),
        currency=CURRENCY, provider=provider,
    )  # fmt: skip
    db.add(order)
    db.flush()
    return order


def first_payment_due(db: Session, sq: Square) -> bool:
    """A launch package (not the Event pass, not a square from before the packages) whose first payment has not been made: the trial, then this (W12-R9)."""
    if sq.launch_package not in UPGRADE_ORDER:
        return False
    paid = db.scalar(select(BillingOrder.id).where(BillingOrder.square_id == sq.id, BillingOrder.kind == "first", BillingOrder.status == "paid").limit(1))
    return paid is None


def new_first_order(db: Session, sq: Square, interval: str, user_id: uuid.UUID | None, provider: str, package: str | None = None) -> BillingOrder:
    """The first payment, taken when the trial ends: the launch package and the first Live period in one checkout (docs/plans/pricing-strategy.md).
    `package` may name a higher package than the one the square started with: it is paid in full and replaces it (W12-R16)."""
    if interval not in ("month", "year"):
        raise BadRequestError("Choose a monthly or yearly period", code="bad_plan")
    if not first_payment_due(db, sq):
        raise ConflictError("The first payment is already made", code="not_due")
    pkg = package or sq.launch_package or ""
    if pkg not in UPGRADE_ORDER or UPGRADE_ORDER.index(pkg) < UPGRADE_ORDER.index(sq.launch_package or ""):
        raise BadRequestError("Choose your package or a higher one", code="bad_plan")
    order = BillingOrder(
        square_id=sq.id, created_by=user_id, kind="first", launch_package=pkg, running_plan=plans.LIVE, interval=interval,
        amount_minor=price_of(db, f"launch.{pkg}") + price_of(db, f"running.{plans.LIVE}.{interval}"), currency=CURRENCY, provider=provider,
    )  # fmt: skip
    db.add(order)
    db.flush()
    return order


def new_running_order(db: Session, sq: Square, plan: str, interval: str, user_id: uuid.UUID | None, provider: str) -> BillingOrder:
    if sq.launch_package == plans.CUSTOM:
        # a custom package (W19-R20, ADR 082): one agreed amount per period, always Live; what the page sent for plan and period does not matter
        if not sq.custom_amount_minor or sq.custom_interval not in ("month", "year"):
            raise ConflictError("The custom package has no agreed amount yet", code="custom_not_set")
        order = BillingOrder(
            square_id=sq.id, created_by=user_id, kind="running", running_plan=plans.LIVE, interval=sq.custom_interval,
            amount_minor=sq.custom_amount_minor, currency=CURRENCY, provider=provider,
        )  # fmt: skip
        db.add(order)
        db.flush()
        return order
    if plan not in (plans.LIVE, plans.KEEP) or interval not in ("month", "year"):
        raise BadRequestError("Choose Live or Keep, monthly or yearly", code="bad_plan")
    if sq.running_plan == plans.EVENT_RUN:
        raise ConflictError("An event pass has no running plan to buy", code="event_pass")
    order = BillingOrder(
        square_id=sq.id, created_by=user_id, kind="running", running_plan=plan, interval=interval,
        amount_minor=price_of(db, f"running.{plan}.{interval}"), currency=CURRENCY, provider=provider,
    )  # fmt: skip
    db.add(order)
    db.flush()
    return order


def apply_event(db: Session, event: PaymentEvent, now: dt.datetime | None = None, settings: Settings | None = None) -> BillingOrder | None:
    """Apply a provider's answer to an order. Idempotent: a second 'paid' for the same order changes nothing (providers retry webhooks)."""
    now = now or dt.datetime.now(dt.UTC)
    if event.ended:
        return _subscription_ended(db, event)
    if event.invoice_id:
        return _apply_renewal(db, event, now, settings)
    order = db.get(BillingOrder, event.order_id) if event.order_id else None
    if order is None:
        return None
    if order.status != "pending":
        return order
    if not event.paid:
        order.status = "cancelled"
        return order
    order.status = "paid"
    order.paid_at = now
    order.card_brand, order.card_last4 = (event.card_brand or None), (event.card_last4 or None)
    order.newly_paid = True  # type: ignore[attr-defined]  # in memory only: the caller starts the build once, not again on a replayed webhook
    sq = db.get(Square, order.square_id)
    if sq is not None:
        _apply_paid(sq, order, now, settings)
        if event.subscription_id and order.kind in ("running", "first"):
            sq.stripe_subscription_id = event.subscription_id
            sq.renewal_cancelled = False
    return order


def _apply_renewal(db: Session, event: PaymentEvent, now: dt.datetime, settings: Settings | None) -> BillingOrder | None:
    """A later period of a subscription was paid: a new paid order and the paid time grows. A replayed invoice changes nothing."""
    origin = db.get(BillingOrder, event.order_id) if event.order_id else None
    if origin is None or not event.invoice_id:
        return None
    if db.scalar(select(BillingOrder.id).where(BillingOrder.provider_ref == event.invoice_id).limit(1)) is not None:
        return None
    sq = db.get(Square, origin.square_id)
    if sq is None:
        return None
    # The plan of the new period is the square's, not the first order's: a downgrade that was waiting for this renewal starts now (W18-R34), and a square
    # that moved between Keep and Live keeps renewing the plan it is on.
    plan = sq.pending_running_plan or (sq.running_plan if sq.running_plan in (plans.LIVE, plans.KEEP) else origin.running_plan)
    order = BillingOrder(
        square_id=origin.square_id, created_by=origin.created_by, kind="running", running_plan=plan, interval=origin.interval,
        amount_minor=event.amount_minor or origin.amount_minor, currency=origin.currency, status="paid", provider=origin.provider,
        provider_ref=event.invoice_id,
        paid_at=now, card_brand=event.card_brand, card_last4=event.card_last4,
    )  # fmt: skip
    db.add(order)
    order.newly_paid = True  # type: ignore[attr-defined]
    if sq.pending_running_plan:
        db.add(AuditLog(action="billing.plan_applied", entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"running_plan": plan}))
        sq.pending_running_plan = None
    _apply_paid(sq, order, now, settings)
    if event.subscription_id:
        sq.stripe_subscription_id = event.subscription_id
    db.flush()
    return order


def _subscription_ended(db: Session, event: PaymentEvent) -> BillingOrder | None:
    """The subscription is over: the square keeps its plan until the paid time ends (the trial-end job then puts it to sleep)."""
    sq = db.scalar(select(Square).where(Square.stripe_subscription_id == event.subscription_id)) if event.subscription_id else None
    if sq is not None:
        sq.stripe_subscription_id = None
        sq.renewal_cancelled = False
        sq.payment_failed_at = None
    return None


def subscription_interval(db: Session, sq: Square) -> str:
    """The period of the square's subscription: the one of its latest paid first or running order, else the owner's default."""
    last = db.scalar(
        select(BillingOrder.interval)
        .where(BillingOrder.square_id == sq.id, BillingOrder.status == "paid", BillingOrder.kind.in_(("first", "running")))
        .order_by(BillingOrder.paid_at.desc())
        .limit(1)
    )
    return last or sq.billing_interval or "month"


def upgrade_charge_minor(old_minor: int, new_minor: int, paid_until: dt.datetime | None, now: dt.datetime, interval: str) -> int:
    """What an upgrade is about to cost now: the price difference for the rest of the paid period (the provider works out the exact amount and the tax)."""
    end = _aware(paid_until)
    days = 365 if interval == "year" else 30
    left = 0.0 if end is None else max(0.0, min(float(days), (end - now).total_seconds() / 86400))
    return max(0, round((new_minor - old_minor) * left / days))


def change_plan_now(
    db: Session, sq: Square, provider: Any, plan: str, tax_percent_value: float, now: dt.datetime | None = None, immediate: bool = False
) -> PlanChange:
    """Put the price of the square's subscription to `plan` (W18-R34). A paid immediate change is stored as a paid order; the caller switches the plan."""
    now = now or dt.datetime.now(dt.UTC)
    if not sq.stripe_subscription_id:
        raise ConflictError("This square has no renewing payment", code="no_subscription")
    interval = subscription_interval(db, sq)
    amount = price_of(db, f"running.{plan}.{interval}")
    charge = upgrade_charge_minor(price_of(db, f"running.{sq.running_plan}.{interval}"), amount, sq.paid_until, now, interval) if immediate else 0
    result: PlanChange = provider.change_plan(sq.stripe_subscription_id, plan, interval, amount, tax_percent_value, immediate, charge)
    if immediate and result.paid:
        db.add(
            BillingOrder(
                square_id=sq.id,
                kind="running",
                running_plan=plan,
                interval=interval,
                amount_minor=result.amount_minor,
                currency=CURRENCY,
                status="paid",
                provider=provider.name,
                provider_ref=result.invoice_id,
                paid_at=now,
            )
        )
    return result


def apply_due_downgrades(db: Session, now: dt.datetime) -> list[Square]:
    """Squares whose paid time has ended and that were waiting to go to Keep (no renewal brought it: no subscription, or the renewal was cancelled)."""
    rows = db.scalars(select(Square).where(Square.pending_running_plan == plans.KEEP, Square.running_plan == plans.LIVE, Square.paid_until.is_not(None))).all()
    return [sq for sq in rows if (_aware(sq.paid_until) or now) <= now]


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    """Some databases give back a time without its zone; it is always UTC here."""
    return value.replace(tzinfo=dt.UTC) if value is not None and value.tzinfo is None else value


REFUNDABLE_KINDS = ("first", "running", "event_pass")


def remaining_minor(order: BillingOrder) -> int:
    """What is left to refund of a payment (its amount minus what already went back)."""
    return int(getattr(order, "amount_minor", 0) or 0) - int(getattr(order, "refunded_minor", 0) or 0)


def refundable(order: BillingOrder, settings: Settings, now: dt.datetime | None = None) -> bool:
    """A paid first payment (launch package plus first Live period), renewal or Event pass, inside the refund days, with something left to refund
    (docs/plans/pricing-strategy.md; renewals, Event pass and partial refunds W13-R31). A payment that was refunded in part is still `paid`."""
    paid = _aware(order.paid_at)
    now = now or dt.datetime.now(dt.UTC)
    left = remaining_minor(order) > 0 if hasattr(order, "amount_minor") else True
    inside = paid is not None and now <= paid + dt.timedelta(days=settings.BILLING_REFUND_DAYS)
    return order.kind in REFUNDABLE_KINDS and order.status == "paid" and left and inside


def refundable_minor(order: BillingOrder, settings: Settings, now: dt.datetime | None = None) -> int:
    return remaining_minor(order) if refundable(order, settings, now) else 0


def mark_refunded(order: BillingOrder, sq: Square, now: dt.datetime | None = None, settings: Settings | None = None) -> None:
    """After ALL of a payment went back: the order is refunded. A first payment or a renewal: the paid time ends now, the renewal is gone and the first
    payment is due again. An Event pass: the live days end now and the archive starts."""
    now = now or dt.datetime.now(dt.UTC)
    order.status = "refunded"
    order.refunded_minor = order.amount_minor
    if order.kind == "event_pass":
        event_pass.end_now(sq, settings.EVENT_PASS_ARCHIVE_DAYS if settings is not None else 45, now)
        return
    sq.paid_until = now
    sq.stripe_subscription_id = None
    sq.renewal_cancelled = False
    sq.payment_failed_at = None


def record_partial_refund(order: BillingOrder, amount_minor: int) -> None:
    """A goodwill refund of part of a payment: only the record changes (the square's plan and dates stay). When nothing is left the order counts as refunded."""
    order.refunded_minor = int(order.refunded_minor or 0) + amount_minor
    if order.refunded_minor >= order.amount_minor:
        order.status = "refunded"


def record_failure(db: Session, event: PaymentEvent, now: dt.datetime | None = None) -> Square | None:
    """A renewal payment failed: remember since when. Returns the square only the first time (the owner is told once, not at every retry of the card)."""
    origin = db.get(BillingOrder, event.order_id) if event.order_id else None
    sq = db.get(Square, origin.square_id) if origin is not None else None
    if sq is None or sq.payment_failed_at is not None:
        return None
    sq.payment_failed_at = now or dt.datetime.now(dt.UTC)
    db.flush()
    return sq


def _apply_paid(sq: Square, order: BillingOrder, now: dt.datetime, settings: Settings | None = None) -> None:
    if order.kind in ("running", "first"):
        sq.payment_failed_at = None  # a payment went through: the failure is over
    if order.kind == "event_pass":
        if settings is not None and event_pass.awaiting_payment(sq):
            event_pass.start(sq, settings, now)  # the clock of the pass runs from payment (ADR 044)
    elif order.kind == "upgrade" and order.launch_package:
        sq.launch_package = order.launch_package  # modules already on stay on; the package only widens what may be switched on
    elif order.kind == "event_upgrade" and order.launch_package:
        # the pass becomes a normal square: Live, paid for the first period, no live end, no archive, no deletion (ADR 044)
        sq.launch_package = order.launch_package
        sq.running_plan = plans.LIVE
        sq.paid_until = now + (dt.timedelta(days=365) if order.interval == "year" else dt.timedelta(days=30))
        event_pass.clear(sq)
    elif order.kind in ("running", "first") and order.running_plan:
        if order.kind == "first" and order.launch_package:
            sq.launch_package = order.launch_package  # the package chosen at the first payment (the same or a higher one)
        # the plan itself (Live or Keep, with the sleep or wake that goes with it) is switched by the caller after the commit (routes `_after_paid`)
        left = _aware(sq.paid_until)
        base = left if left and left > now else now  # paying early adds to the time left
        sq.paid_until = base + (dt.timedelta(days=365) if order.interval == "year" else dt.timedelta(days=30))


def wake_needs_payment(settings: Settings, sq: Square, now: dt.datetime | None = None) -> bool:
    """With BILLING_ENFORCE a sleeping square wakes only while a running period is paid."""
    if not settings.BILLING_ENFORCE:
        return False
    now = now or dt.datetime.now(dt.UTC)
    until = _aware(sq.paid_until)
    return until is None or until <= now
