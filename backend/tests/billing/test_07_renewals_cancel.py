# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Renewals extend the paid time once; cancel and resume."""

import datetime as dt

from flask import Flask
from sqlalchemy import select

from app.platform.models import Square
from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_renewals_extend_the_paid_time_once_and_cancel_keeps_it_until_the_end(api: Flask) -> None:
    from app.platform import billing

    c, h, sq = _square(api, "rn1", "roots")
    co = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=h).json
    first_id = co["order_id"]
    db = api.extensions["db_factory"]()()
    try:
        ev = billing.PaymentEvent(order_id=__import__("uuid").UUID(first_id), paid=True, subscription_id="sub_1")
        billing.apply_event(db, ev, now=NOW)
        db.commit()
        row = db.scalar(select(Square).where(Square.slug == "sq-rn1"))
        assert row.stripe_subscription_id == "sub_1"
        before = row.paid_until
        renew = billing.PaymentEvent(order_id=__import__("uuid").UUID(first_id), subscription_id="sub_1", invoice_id="in_2", amount_minor=2500)
        order = billing.apply_event(db, renew, now=NOW + dt.timedelta(days=30))
        db.commit()
        assert order.kind == "running" and order.status == "paid" and order.amount_minor == 2500 and order.provider_ref == "in_2"
        db.refresh(row)
        assert row.paid_until > before
        again = row.paid_until
        assert billing.apply_event(db, renew, now=NOW + dt.timedelta(days=31)) is None  # a replayed invoice changes nothing
        db.refresh(row)
        assert row.paid_until == again
    finally:
        db.close()
    got = c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json
    assert got["subscription"] == "renewing"
    assert c.post(f"/api/platform/v1/squares/{sq['id']}/billing/cancel-renewal", headers=h).json["subscription"] == "ending"
    assert c.post(f"/api/platform/v1/squares/{sq['id']}/billing/resume-renewal", headers=h).json["subscription"] == "renewing"
    db = api.extensions["db_factory"]()()
    try:
        billing.apply_event(db, billing.PaymentEvent(subscription_id="sub_1", ended=True))
        db.commit()
    finally:
        db.close()
    assert c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json["subscription"] is None
    assert c.post(f"/api/platform/v1/squares/{sq['id']}/billing/cancel-renewal", headers=h).status_code == 409
