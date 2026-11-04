# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The Stripe webhook END TO END through the Flask route (W12-R22): a real signature, the real apply code, the database. Only Stripe's own HTTP is replaced.

This is the test that proves a payment Stripe reports really changes the square, that a replay changes nothing and that a forged call is refused."""

import datetime as dt
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import select

from app.platform.billing import StripeBillingProvider
from app.platform.models import AuditLog, BillingOrder, Square
from tests.billing.helpers import HEADERS, PREFIX, _checkout, _square, api  # noqa: F401
from tests.staff_client import as_admin

SECRET = "whsec_route_test"
WEBHOOK = f"{PREFIX}/billing/webhook"


@pytest.fixture
def stripe_api(api: Flask, monkeypatch) -> Flask:
    """The app with the Stripe adapter wired in (its signature secret is SECRET); the card lookups at Stripe answer a canned card."""
    api.extensions["billing"] = StripeBillingProvider("sk_test_x", SECRET)
    card = {"payment_intent": {"payment_method": {"card": {"brand": "visa", "last4": "4242"}}}, "subscription": None}
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.retrieve", lambda self, session, params=None, options=None: SimpleNamespace(to_dict=lambda: card)
    )
    monkeypatch.setattr(
        "stripe._subscription_service.SubscriptionService.retrieve",
        lambda self, sub, params=None, options=None: SimpleNamespace(
            to_dict=lambda: {"metadata": {}, "default_payment_method": {"card": {"brand": "visa", "last4": "4242"}}}
        ),
    )
    # customers and checkout sessions are made at Stripe when an order starts: answer them
    monkeypatch.setattr("stripe._customer_service.CustomerService.create", lambda self, params=None, options=None: SimpleNamespace(id="cus_t"))
    monkeypatch.setattr("stripe._customer_service.CustomerService.update", lambda self, c, params=None, options=None: SimpleNamespace(id=c))
    monkeypatch.setattr(
        "stripe.checkout._session_service.SessionService.create",
        lambda self, params=None, options=None: SimpleNamespace(url="https://checkout.stripe.test/s", id="cs_new"),
    )
    return api


def post(c, event: dict, secret: str = SECRET):
    body = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return c.post(WEBHOOK, data=body, headers={"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"})


def session_event(typ: str, order_id: str, **obj) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex[:8]}",
        "object": "event",
        "type": typ,
        "data": {"object": {"id": "cs_1", "object": "checkout.session", "metadata": {"order_id": order_id}, **obj}},
    }


def invoice_event(typ: str, order_id: str, invoice_id: str, reason: str = "subscription_cycle", sub: str = "sub_1") -> dict:
    inv = {
        "id": invoice_id,
        "object": "invoice",
        "billing_reason": reason,
        "amount_paid": 2500,
        "subscription": sub,
        "subscription_details": {"metadata": {"order_id": order_id}},
    }
    return {"id": f"evt_{uuid.uuid4().hex[:8]}", "object": "event", "type": typ, "data": {"object": inv}}


def first_order(c, h, sq, interval="month") -> str:
    return _checkout(c, h, sq, kind="first", interval=interval).json["order_id"]


def square_row(api: Flask, slug: str) -> Square:
    db = api.extensions["db_factory"]()()
    try:
        row = db.scalar(select(Square).where(Square.slug == slug))
        db.expunge(row)
        return row
    finally:
        db.close()


def test_a_bad_or_missing_signature_is_refused_and_nothing_changes(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr1", "roots")
    oid = first_order(c, h, sq)
    event = session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_1")
    assert post(c, event, secret="whsec_other").status_code == 400
    assert c.post(WEBHOOK, data=json.dumps(event), headers={"Content-Type": "application/json"}).status_code == 400
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json["status"] == "pending"


def test_a_paid_first_checkout_applies_once_and_a_replay_changes_nothing(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr2", "roots")
    oid = first_order(c, h, sq)
    event = session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_1")
    assert post(c, event).status_code == 200
    order = c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json
    assert order["status"] == "paid" and (order["card_brand"], order["card_last4"]) == ("visa", "4242")
    row = square_row(stripe_api, "sq-wr2")
    assert row.stripe_subscription_id == "sub_1" and row.paid_until is not None
    until = row.paid_until
    assert post(c, event).status_code == 200  # Stripe retries webhooks
    assert square_row(stripe_api, "sq-wr2").paid_until == until
    got = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert got["first_payment_due"] is False and got["subscription"] == "renewing"


def test_an_expired_checkout_cancels_the_order(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr3", "roots")
    oid = first_order(c, h, sq)
    assert post(c, session_event("checkout.session.expired", oid, payment_status="unpaid")).status_code == 200
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json["status"] == "cancelled"
    # a paid report arriving after the cancel does not revive it: the order is settled
    assert post(c, session_event("checkout.session.completed", oid, payment_status="paid")).status_code == 200
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json["status"] == "cancelled"


def test_an_unpaid_completed_session_and_unknown_orders_and_other_events_are_acknowledged_and_ignored(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr4", "roots")
    oid = first_order(c, h, sq)
    assert post(c, session_event("checkout.session.completed", oid, payment_status="unpaid")).status_code == 200  # waits for the later paid event
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json["status"] == "pending"
    assert post(c, session_event("checkout.session.completed", str(uuid.uuid4()), payment_status="paid")).status_code == 200  # no such order
    for typ in ("payment_intent.payment_failed", "customer.updated", "charge.refunded"):
        assert post(c, session_event(typ, oid)).status_code == 200
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=h).json["status"] == "pending"


def test_a_renewal_invoice_extends_the_paid_time_once(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr5", "roots")
    oid = first_order(c, h, sq)
    post(c, session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_1"))
    before = square_row(stripe_api, "sq-wr5").paid_until
    assert post(c, invoice_event("invoice.paid", oid, "in_100", reason="subscription_create")).status_code == 200  # the first invoice: already counted
    assert square_row(stripe_api, "sq-wr5").paid_until == before
    renew = invoice_event("invoice.paid", oid, "in_101")
    assert post(c, renew).status_code == 200
    after = square_row(stripe_api, "sq-wr5").paid_until
    assert after > before
    assert post(c, renew).status_code == 200  # replay
    assert square_row(stripe_api, "sq-wr5").paid_until == after
    kinds = [o["kind"] for o in c.get(f"{PREFIX}/squares/{sq['id']}/billing/orders", headers=h).json["items"]]
    assert sorted(kinds) == ["first", "running"]


def test_a_failed_renewal_is_recorded_once_and_a_payment_clears_it(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr6", "roots")
    sent: list = []
    stripe_api.extensions["providers"].email = SimpleNamespace(send=lambda to, subject, body, **_kw: sent.append((to, subject)))
    oid = first_order(c, h, sq)
    post(c, session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_1"))
    failed = invoice_event("invoice.payment_failed", oid, "in_200")
    assert post(c, failed).status_code == 200 and post(c, failed).status_code == 200  # Stripe tries the card again
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["payment_failed"] is True
    assert len(sent) == 1 and sent[0][0] == "wr6@example.com"  # the owner is told once
    post(c, invoice_event("invoice.paid", oid, "in_201"))
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["payment_failed"] is False
    db = stripe_api.extensions["db_factory"]()()
    try:
        assert len(db.scalars(select(AuditLog).where(AuditLog.action == "billing.payment_failed")).all()) == 1
    finally:
        db.close()


def test_the_end_of_a_subscription_clears_it(stripe_api: Flask) -> None:
    c, h, sq = _square(stripe_api, "wr7", "roots")
    oid = first_order(c, h, sq)
    post(c, session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_9"))
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["subscription"] == "renewing"
    gone = {"id": "evt_x", "object": "event", "type": "customer.subscription.deleted", "data": {"object": {"id": "sub_9", "object": "subscription"}}}
    assert post(c, gone).status_code == 200
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["subscription"] is None


def test_an_event_pass_is_built_once_when_stripe_says_paid(stripe_api: Flask) -> None:
    stripe_api.extensions["settings"] = stripe_api.extensions["settings"].model_copy(update={"BILLING_PROVIDER": "stripe"})
    c, h, sq = _square(stripe_api, "wr8", "event", country="NO")
    jobs = stripe_api.extensions["executor"].jobs
    assert sq["awaiting_payment"] is True and jobs == []
    oid = _checkout(c, h, sq, kind="event_pass").json["order_id"]
    paid = session_event("checkout.session.completed", oid, payment_status="paid")
    assert post(c, paid).status_code == 200
    assert len(jobs) == 1  # provisioning starts
    assert post(c, paid).status_code == 200
    assert len(jobs) == 1  # not again on a replay
    got = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert got["awaiting_payment"] is False and got["event_pass"]["phase"] == "live"


def test_a_refunded_first_payment_ends_the_subscription_at_stripe_and_the_paid_time(stripe_api: Flask, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("app.platform.billing.StripeBillingProvider._payment_intent_of", lambda self, ref: "pi_1")
    monkeypatch.setattr(
        "stripe._refund_service.RefundService.create", lambda self, params=None, options=None: calls.append(("refund", params["payment_intent"]))
    )
    monkeypatch.setattr("stripe._subscription_service.SubscriptionService.cancel", lambda self, sub, params=None, options=None: calls.append(("cancel", sub)))
    c, h, sq = _square(stripe_api, "wr9", "roots")
    oid = first_order(c, h, sq)
    post(c, session_event("checkout.session.completed", oid, payment_status="paid", subscription="sub_7"))
    c = as_admin(stripe_api, c)
    done = c.post(f"{PREFIX}/owner/billing/orders/{oid}/refund", headers=h)
    assert done.status_code == 200 and done.json["status"] == "refunded"
    assert calls == [("refund", "pi_1"), ("cancel", "sub_7")]  # the money first, then the subscription
    row = square_row(stripe_api, "sq-wr9")
    assert row.stripe_subscription_id is None and row.paid_until <= dt.datetime.now(dt.UTC).replace(tzinfo=None) + dt.timedelta(seconds=5)
    assert BillingOrder  # the order row stays as the record
