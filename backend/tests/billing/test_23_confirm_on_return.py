# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""W25-R27: a payment whose webhook never came is found by asking the provider when the owner comes back to the Billing page."""

import uuid
from types import SimpleNamespace

import stripe
from flask import Flask
from sqlalchemy import select

from app.platform.billing import PaymentEvent, StripeBillingProvider
from app.platform.models import BillingOrder, Square
from tests.billing.helpers import PREFIX, _checkout, _square, api  # noqa: F401


class StubProvider:
    """A payment provider that answers what `check_checkout` is told to answer."""

    name = "stripe"

    def __init__(self) -> None:
        self.answer: PaymentEvent | None = None
        self.asked = 0

    def check_checkout(self, order):
        self.asked += 1
        return None if self.answer is None else PaymentEvent(order_id=order.id, paid=self.answer.paid)


def _pending_stripe_upgrade(api: Flask, who: str):
    c, h, sq = _square(api, who, "roots")
    order_id = _checkout(c, h, sq, kind="upgrade", launch_package="square").json["order_id"]
    db = api.extensions["db_factory"]()()
    try:
        order = db.get(BillingOrder, uuid.UUID(order_id))
        order.provider, order.provider_ref = "stripe", "cs_test_pending"  # as if it was made by Stripe
        db.commit()
    finally:
        db.close()
    return c, h, sq, order_id


def _package(api: Flask, slug: str) -> str | None:
    db = api.extensions["db_factory"]()()
    try:
        return db.scalar(select(Square.launch_package).where(Square.slug == slug))
    finally:
        db.close()


def test_a_paid_checkout_whose_webhook_never_came_is_applied_when_the_owner_comes_back(api: Flask) -> None:
    c, h, sq, oid = _pending_stripe_upgrade(api, "cf1")
    stub = StubProvider()
    api.extensions["billing"] = stub
    url = f"{PREFIX}/squares/{sq['id']}/billing/orders/{oid}/confirm"
    r = c.post(url, headers=h)  # Stripe says nothing yet: it stays pending, the plan is unchanged
    assert r.status_code == 200 and r.json["status"] == "pending" and _package(api, "sq-cf1") == "roots"
    stub.answer = PaymentEvent(paid=True)
    r = c.post(url, headers=h)  # Stripe says paid: the order is applied like a webhook would
    assert r.json["status"] == "paid" and _package(api, "sq-cf1") == "square"
    asked = stub.asked
    assert c.post(url, headers=h).json["status"] == "paid" and stub.asked == asked  # a second look changes nothing and asks nobody


def test_an_expired_checkout_cancels_the_order_and_a_fake_order_is_never_asked(api: Flask) -> None:
    c, h, sq, oid = _pending_stripe_upgrade(api, "cf2")
    c3, h3, sq3 = _square(api, "cf3", "roots")
    fake_id = _checkout(c3, h3, sq3, kind="upgrade", launch_package="square").json["order_id"]  # provider fake
    stub = StubProvider()
    stub.answer = PaymentEvent(paid=False)
    api.extensions["billing"] = stub
    assert c.post(f"{PREFIX}/squares/{sq['id']}/billing/orders/{oid}/confirm", headers=h).json["status"] == "cancelled"
    assert _package(api, "sq-cf2") == "roots"
    before = stub.asked
    assert c3.post(f"{PREFIX}/squares/{sq3['id']}/billing/orders/{fake_id}/confirm", headers=h3).json["status"] == "pending"
    assert stub.asked == before


def test_only_the_owners_organisation_can_ask_and_only_about_its_own_orders(api: Flask) -> None:
    c, h, sq, oid = _pending_stripe_upgrade(api, "cf4")
    other, ho, sq_other = _square(api, "cf5", "roots")
    api.extensions["billing"] = StubProvider()
    assert other.post(f"{PREFIX}/squares/{sq['id']}/billing/orders/{oid}/confirm", headers=ho).status_code == 404  # not their square
    assert other.post(f"{PREFIX}/squares/{sq_other['id']}/billing/orders/{oid}/confirm", headers=ho).status_code == 404  # not their order


def test_the_stripe_adapter_reads_a_session_and_ignores_the_wrong_one(monkeypatch) -> None:
    provider = StripeBillingProvider("sk_test_x", "whsec_x")
    order = SimpleNamespace(id=uuid.uuid4(), provider_ref="cs_test_1")

    def answer(data):
        monkeypatch.setattr(
            "stripe.checkout._session_service.SessionService.retrieve",
            lambda self, session, params=None, options=None: SimpleNamespace(to_dict=lambda: data),
        )

    paid = {"payment_status": "paid", "status": "complete", "metadata": {"order_id": str(order.id)}, "subscription": "sub_1", "payment_intent": None}
    answer(paid)
    event = provider.check_checkout(order)  # type: ignore[arg-type]
    assert event is not None and event.paid and event.order_id == order.id and event.subscription_id == "sub_1"
    answer({**paid, "payment_status": "unpaid", "status": "open"})
    assert provider.check_checkout(order) is None  # still open  # type: ignore[arg-type]
    answer({**paid, "payment_status": "unpaid", "status": "expired"})
    ended = provider.check_checkout(order)  # type: ignore[arg-type]
    assert ended is not None and ended.paid is False
    answer({**paid, "metadata": {"order_id": str(uuid.uuid4())}})
    assert provider.check_checkout(order) is None  # a session of another order never counts  # type: ignore[arg-type]
    assert provider.check_checkout(SimpleNamespace(id=order.id, provider_ref="fake_1")) is None  # type: ignore[arg-type]

    def boom(self, session, params=None, options=None):
        raise stripe.APIConnectionError("secret detail sk_test_x")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.retrieve", boom)
    assert provider.check_checkout(order) is None  # a failed lookup leaves the order pending  # type: ignore[arg-type]
