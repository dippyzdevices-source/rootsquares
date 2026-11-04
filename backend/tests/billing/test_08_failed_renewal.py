# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""A failed renewal: remembered once, e-mail, cleared by a payment."""

import datetime as dt

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_a_failed_renewal_is_remembered_once_cleared_by_a_payment_and_the_owner_is_told(api: Flask) -> None:
    import uuid

    from app.platform import billing, notify

    c, h, sq = _square(api, "pf1", "roots")
    first = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=h).json["order_id"]
    oid = uuid.UUID(first)
    db = api.extensions["db_factory"]()()
    try:
        billing.apply_event(db, billing.PaymentEvent(order_id=oid, subscription_id="sub_f"), now=NOW)
        db.commit()
        fail = billing.PaymentEvent(order_id=oid, paid=False, failed=True, subscription_id="sub_f", invoice_id="in_f")
        row = billing.record_failure(db, fail, now=NOW)
        db.commit()
        assert row is not None and row.payment_failed_at is not None
        assert billing.record_failure(db, fail, now=NOW) is None  # a retry of the same failure: no second mail
        subject, text = notify.payment_failed_text(api.extensions["settings"], row)
        assert "Sq pf1" in subject and "update your card" in text.lower() and f"/squares/{row.id}/payments" in text
        sent = []
        api.extensions["providers"].email = type("M", (), {"send": lambda self, to, s, b: sent.append((to, s))})()
        assert notify.send_to_owner(api, db, row, subject, text) is True and sent[0][0] == "pf1@example.com"
    finally:
        db.close()
    got = c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json
    assert got["payment_failed"] is True and got["grace_ends"] is not None
    db = api.extensions["db_factory"]()()
    try:
        billing.apply_event(
            db, billing.PaymentEvent(order_id=oid, subscription_id="sub_f", invoice_id="in_ok", amount_minor=2500), now=NOW + dt.timedelta(days=30)
        )
        db.commit()
    finally:
        db.close()
    assert c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json["payment_failed"] is False  # a payment went through
