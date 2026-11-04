"""Stripe adapter (W12-R4): Stripe's HTTP is mocked; the webhook signature is real (signed with a test secret)."""

import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import pytest
import stripe

from app.platform.billing import PaymentEvent, StripeBillingProvider
from app.shared.errors import AppError, BadRequestError

SECRET = "whsec_test_secret"


def _provider() -> StripeBillingProvider:
    return StripeBillingProvider("sk_test_x", SECRET)


def _order(kind="upgrade", **kw):
    base = dict(id=uuid.uuid4(), kind=kind, launch_package="grove", running_plan=None, interval=None, amount_minor=10_000, currency="USD")
    base.update(kw)
    return SimpleNamespace(**base)


def _signed(event: dict, secret: str = SECRET) -> tuple[dict[str, str], bytes]:
    body = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={sig}"}, body


def _session_event(typ: str, oid: uuid.UUID, **obj):
    return {
        "id": "evt_1",
        "object": "event",
        "type": typ,
        "data": {"object": {"id": "cs_1", "object": "checkout.session", "metadata": {"order_id": str(oid)}, **obj}},
    }


@pytest.mark.parametrize(
    ("order", "mode", "recurring"),
    [
        (_order(), "payment", None),
        (_order("event_upgrade", interval="year"), "payment", None),
        (_order("running", running_plan="live", interval="year"), "subscription", "year"),
    ],
)
def test_create_checkout_builds_the_session(monkeypatch, order, mode, recurring):
    seen = {}

    def fake_create(self, params=None, options=None):
        seen.update(params)
        return SimpleNamespace(url="https://checkout.stripe.test/s", id="cs_test_1")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.create", fake_create)
    out = _provider().create_checkout(order, "https://ok", "https://no")
    assert (out.url, out.ref) == ("https://checkout.stripe.test/s", "cs_test_1")
    assert seen["mode"] == mode and seen["client_reference_id"] == str(order.id) and seen["metadata"] == {"order_id": str(order.id)}
    pd = seen["line_items"][0]["price_data"]
    assert pd["currency"] == "usd" and pd["unit_amount"] == 10_000
    assert (pd.get("recurring") or {}).get("interval") == recurring


def test_create_checkout_hides_provider_errors(monkeypatch):
    def boom(self, params=None, options=None):
        raise stripe.APIConnectionError("secret detail sk_test_x")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.create", boom)
    with pytest.raises(AppError) as err:
        _provider().create_checkout(_order(), "https://ok", "https://no")
    assert "sk_test" not in str(err.value)


@pytest.fixture(autouse=True)
def _card(monkeypatch):
    """The card lookup would call Stripe; give it a canned answer."""
    canned = {"payment_intent": {"payment_method": {"card": {"brand": "visa", "last4": "4242"}}}, "subscription": None}
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.retrieve",
        lambda self, session, params=None, options=None: SimpleNamespace(to_dict=lambda: canned),
    )


def test_webhook_paid_and_expired():
    oid = uuid.uuid4()
    h, b = _signed(_session_event("checkout.session.completed", oid, payment_status="paid"))
    assert _provider().read_webhook(h, b) == PaymentEvent(order_id=oid, paid=True, card_brand="visa", card_last4="4242")
    h, b = _signed(_session_event("checkout.session.expired", oid, payment_status="unpaid"))
    assert _provider().read_webhook(h, b) == PaymentEvent(order_id=oid, paid=False)


def test_webhook_unpaid_completed_and_other_events_are_ignored():
    oid = uuid.uuid4()
    h, b = _signed(_session_event("checkout.session.completed", oid, payment_status="unpaid"))
    assert _provider().read_webhook(h, b) is None
    for typ in ("invoice.paid", "payment_intent.payment_failed", "customer.subscription.updated"):
        h, b = _signed(_session_event(typ, oid))
        assert _provider().read_webhook(h, b) is None


def test_webhook_bad_signature_is_refused():
    h, b = _signed(_session_event("checkout.session.completed", uuid.uuid4(), payment_status="paid"), secret="whsec_other")
    with pytest.raises(BadRequestError):
        _provider().read_webhook(h, b)
    with pytest.raises(BadRequestError):
        _provider().read_webhook({}, b)


def test_first_payment_is_a_subscription_with_the_package_as_a_one_time_line(monkeypatch):
    seen = {}

    def fake_create(self, params=None, options=None):
        seen.update(params)
        return SimpleNamespace(url="https://checkout.stripe.test/s", id="cs_test_2")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.create", fake_create)
    order = _order("first", running_plan="live", interval="month", amount_minor=17_400)
    _provider().create_checkout(order, "https://ok", "https://no", launch_minor=14_900)
    assert seen["mode"] == "subscription"
    once, period = seen["line_items"][1]["price_data"], seen["line_items"][0]["price_data"]
    assert once["unit_amount"] == 14_900 and "recurring" not in once
    assert period["unit_amount"] == 2_500 and period["recurring"] == {"interval": "month"}


def test_a_customer_is_made_once_with_the_country_and_used_by_the_checkout(monkeypatch):
    made = []

    def fake_customer(self, params=None, options=None):
        made.append(params)
        return SimpleNamespace(id="cus_1")

    monkeypatch.setattr("stripe._customer_service.CustomerService.create", fake_customer)
    p = _provider()
    assert p.ensure_customer(None, "Club", "a@b.c", "NO") == "cus_1" and made[0]["address"] == {"country": "NO"}
    updated = []
    monkeypatch.setattr("stripe._customer_service.CustomerService.update", lambda self, c, params=None, options=None: updated.append((c, params)))
    assert p.ensure_customer("cus_9", "Club", "a@b.c", "NO") == "cus_9" and len(made) == 1  # kept, not made again
    assert updated == [("cus_9", {"address": {"country": "NO"}})]
    seen = {}

    def fake_create(self, params=None, options=None):
        seen.update(params)
        return SimpleNamespace(url="https://checkout.stripe.test/s", id="cs_test_3")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.create", fake_create)
    p.create_checkout(_order(), "https://ok", "https://no", customer="cus_1")
    assert seen["customer"] == "cus_1" and seen["customer_update"] == {"address": "auto", "name": "auto"}


def _invoice(reason: str, new_shape: bool, oid: uuid.UUID):
    base = {"id": "in_9", "object": "invoice", "billing_reason": reason, "amount_paid": 2500}
    meta = {"order_id": str(oid)}
    if new_shape:
        base["parent"] = {"subscription_details": {"subscription": "sub_9", "metadata": meta}}
    else:
        base.update(subscription="sub_9", subscription_details={"metadata": meta})
    return {"id": "evt_2", "object": "event", "type": "invoice.paid", "data": {"object": base}}


@pytest.mark.parametrize("new_shape", [False, True])
def test_a_renewal_invoice_becomes_a_renewal_event_and_the_first_invoice_is_ignored(monkeypatch, new_shape):
    monkeypatch.setattr(
        "stripe._subscription_service.SubscriptionService.retrieve",
        lambda self, sub, params=None, options=None: SimpleNamespace(to_dict=lambda: {"default_payment_method": {"card": {"brand": "visa", "last4": "4242"}}}),
    )
    oid = uuid.uuid4()
    h, b = _signed(_invoice("subscription_cycle", new_shape, oid))
    ev = _provider().read_webhook(h, b)
    assert (ev.order_id, ev.invoice_id, ev.subscription_id, ev.amount_minor, ev.card_last4) == (oid, "in_9", "sub_9", 2500, "4242")
    h, b = _signed(_invoice("subscription_create", new_shape, oid))
    assert _provider().read_webhook(h, b) is None  # the checkout itself already counted it


def test_subscription_deleted_and_the_renewal_switch(monkeypatch):
    h, b = _signed({"id": "evt_3", "object": "event", "type": "customer.subscription.deleted", "data": {"object": {"id": "sub_9", "object": "subscription"}}})
    ev = _provider().read_webhook(h, b)
    assert ev.ended is True and ev.subscription_id == "sub_9"
    seen = []
    monkeypatch.setattr("stripe._subscription_service.SubscriptionService.update", lambda self, sub, params=None, options=None: seen.append((sub, params)))
    _provider().set_renewal("sub_9", renew=False)
    _provider().set_renewal("sub_9", renew=True)
    assert seen == [("sub_9", {"cancel_at_period_end": True}), ("sub_9", {"cancel_at_period_end": False})]


def test_the_portal_session_is_made_for_the_customer(monkeypatch):
    seen = {}

    def fake_create(self, params=None, options=None):
        seen.update(params)
        return SimpleNamespace(url="https://billing.stripe.test/p/abc")

    monkeypatch.setattr("stripe.billing_portal._session_service.SessionService.create", fake_create)
    assert _provider().create_portal("cus_1", "https://back") == "https://billing.stripe.test/p/abc"
    assert seen == {"customer": "cus_1", "return_url": "https://back"}


def test_a_failed_renewal_invoice_becomes_a_failure_event():
    oid = uuid.uuid4()
    ev = _invoice("subscription_cycle", True, oid)
    ev["type"] = "invoice.payment_failed"
    h, b = _signed(ev)
    got = _provider().read_webhook(h, b)
    assert (got.order_id, got.failed, got.paid, got.invoice_id, got.subscription_id) == (oid, True, False, "in_9", "sub_9")
    ev2 = _invoice("subscription_create", True, oid)
    ev2["type"] = "invoice.payment_failed"
    h, b = _signed(ev2)
    assert _provider().read_webhook(h, b) is None  # the first payment is handled by the checkout page


def test_a_refund_finds_the_payment_and_is_repeat_safe(monkeypatch):
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.retrieve",
        lambda self, session, params=None, options=None: SimpleNamespace(
            to_dict=lambda: {"payment_intent": None, "invoice": {"id": "in_1", "payment_intent": "pi_77"}}
        ),
    )
    seen = []
    monkeypatch.setattr(
        "stripe._refund_service.RefundService.create", lambda self, params=None, options=None: seen.append((params, options)) or SimpleNamespace(id="re_1")
    )
    oid = uuid.uuid4()
    _provider().refund(SimpleNamespace(id=oid, provider_ref="cs_1"))
    assert seen[0][0]["payment_intent"] == "pi_77" and seen[0][1] == {"idempotency_key": f"refund-{oid}"}


def test_a_refund_with_no_payment_found_is_an_error_and_ending_a_subscription(monkeypatch):
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.retrieve",
        lambda self, session, params=None, options=None: SimpleNamespace(to_dict=lambda: {"payment_intent": None, "invoice": None}),
    )
    with pytest.raises(AppError):
        _provider().refund(SimpleNamespace(id=uuid.uuid4(), provider_ref="cs_1"))
    ended = []
    monkeypatch.setattr("stripe._subscription_service.SubscriptionService.cancel", lambda self, sub, params=None, options=None: ended.append(sub))
    _provider().end_subscription("sub_1")
    assert ended == ["sub_1"]


def test_a_test_clock_is_attached_to_new_customers_only_when_configured(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "stripe._customer_service.CustomerService.create", lambda self, params=None, options=None: seen.append(params) or SimpleNamespace(id="cus_c")
    )
    StripeBillingProvider("sk_test_x", SECRET, test_clock="clock_1").ensure_customer(None, "Club", "a@b.c", "NO")
    StripeBillingProvider("sk_test_x", SECRET).ensure_customer(None, "Club", "a@b.c", "NO")
    assert seen[0]["test_clock"] == "clock_1" and "test_clock" not in seen[1]


def test_a_partial_refund_sends_the_amount_with_its_own_idempotency_key(monkeypatch):
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.retrieve",
        lambda self, session, params=None, options=None: SimpleNamespace(to_dict=lambda: {"payment_intent": "pi_9", "invoice": None}),
    )
    seen = []
    monkeypatch.setattr(
        "stripe._refund_service.RefundService.create", lambda self, params=None, options=None: seen.append((params, options)) or SimpleNamespace(id="re_2")
    )
    oid = uuid.uuid4()
    _provider().refund(SimpleNamespace(id=oid, provider_ref="cs_9", refunded_minor=500), 1_000)
    assert seen[0][0]["payment_intent"] == "pi_9" and seen[0][0]["amount"] == 1_000
    assert seen[0][1] == {"idempotency_key": f"refund-{oid}-500-1000"}  # another amount, or the same one after a refund, is another refund


def test_a_renewal_is_refunded_through_its_invoice(monkeypatch):
    monkeypatch.setattr(
        "stripe._invoice_service.InvoiceService.retrieve",
        lambda self, invoice, params=None, options=None: SimpleNamespace(to_dict=lambda: {"id": "in_5", "payment_intent": "pi_55"}),
    )
    seen = []
    monkeypatch.setattr(
        "stripe._refund_service.RefundService.create", lambda self, params=None, options=None: seen.append(params) or SimpleNamespace(id="re_3")
    )
    _provider().refund(SimpleNamespace(id=uuid.uuid4(), provider_ref="in_5"))
    assert seen[0]["payment_intent"] == "pi_55" and "amount" not in seen[0]  # no amount: the whole payment
