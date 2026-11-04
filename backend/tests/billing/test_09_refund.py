# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The 14-day refund of a first payment (platform admin)."""

import datetime as dt

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401
from tests.staff_client import as_admin


def test_an_admin_refunds_a_first_payment_inside_the_days_and_only_then(api: Flask) -> None:
    import uuid

    from app.platform import billing

    c, h, sq = _square(api, "rf1", "roots")
    first = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=h).json["order_id"]
    ha = {**h, "Authorization": "Bearer fake:u-rf1:rf1@example.com"}
    assert c.post(f"/api/platform/v1/billing/orders/{first}/fake-confirm", json={"outcome": "paid"}, headers=ha).status_code == 200
    # not an admin: refused
    assert c.post(f"/api/platform/v1/owner/billing/orders/{first}/refund", headers=h).status_code == 404
    c = as_admin(api, c)
    detail = c.get(f"/api/platform/v1/owner/squares/{sq['id']}", headers=h).json
    assert [(o["kind"], o["refundable"]) for o in detail["orders"]] == [("first", True)]
    done = c.post(f"/api/platform/v1/owner/billing/orders/{first}/refund", headers=h)
    assert done.status_code == 200 and done.json["status"] == "refunded"
    now = c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json
    assert now["first_payment_due"] is True and now["running_plan"] == "keep" and now["subscription"] is None  # unpaid again, asleep
    assert c.post(f"/api/platform/v1/owner/billing/orders/{first}/refund", headers=h).status_code == 409  # only once
    # past the days: not refundable
    other = _square(api, "rf2", "square")
    oid = (
        other[0]
        .post(f"/api/platform/v1/squares/{other[2]['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=other[1])
        .json["order_id"]
    )
    db = api.extensions["db_factory"]()()
    try:
        from app.platform.models import BillingOrder

        o = db.get(BillingOrder, uuid.UUID(oid))
        o.status, o.paid_at = "paid", NOW - dt.timedelta(days=15)
        db.commit()
        assert billing.refundable(o, api.extensions["settings"], now=NOW) is False
        assert billing.refundable(o, api.extensions["settings"], now=NOW - dt.timedelta(days=2)) is True
    finally:
        db.close()


def _paid_first(api: Flask, who: str, package: str = "roots"):
    """A square with a paid first payment, and its admin: returns (client, headers, square, order id)."""
    c, h, sq = _square(api, who, package)
    oid = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=h).json["order_id"]
    assert c.post(f"/api/platform/v1/billing/orders/{oid}/fake-confirm", json={"outcome": "paid"}, headers=h).status_code == 200
    c = as_admin(api, c)
    return c, h, sq, oid


def test_a_partial_refund_moves_money_only_and_keeps_track_of_what_is_left(api: Flask) -> None:
    c, h, sq, oid = _paid_first(api, "pr1")
    url = f"/api/platform/v1/owner/billing/orders/{oid}/refund"
    order = c.get(f"/api/platform/v1/owner/squares/{sq['id']}", headers=h).json["orders"][0]
    amount = order["amount_minor"]
    assert order["refundable_minor"] == amount and order["refunded_minor"] == 0
    part = c.post(url, json={"amount_minor": 1_000}, headers=h)
    assert part.status_code == 200 and part.json["status"] == "paid" and part.json["refunded_minor"] == 1_000  # still paid: only some went back
    now = c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json
    assert now["first_payment_due"] is False and now["running_plan"] == "live"  # nothing else changed: no sleep, plan and dates stay
    left = c.get(f"/api/platform/v1/owner/squares/{sq['id']}", headers=h).json["orders"][0]
    assert left["refundable"] is True and left["refundable_minor"] == amount - 1_000
    assert c.post(url, headers=h).status_code == 409  # a full refund (with effects) is no longer possible once part went back
    assert c.post(url, json={"amount_minor": amount}, headers=h).status_code == 422  # more than is left
    assert c.post(url, json={"amount_minor": 0}, headers=h).status_code == 422
    last = c.post(url, json={"amount_minor": amount - 1_000}, headers=h)
    assert last.status_code == 200 and last.json["status"] == "refunded" and last.json["refunded_minor"] == amount  # nothing left
    assert c.post(url, json={"amount_minor": 1}, headers=h).status_code == 409


def test_an_amount_equal_to_the_whole_payment_is_a_full_refund_with_its_effects(api: Flask) -> None:
    c, h, sq, oid = _paid_first(api, "pr2")
    amount = c.get(f"/api/platform/v1/owner/squares/{sq['id']}", headers=h).json["orders"][0]["amount_minor"]
    done = c.post(f"/api/platform/v1/owner/billing/orders/{oid}/refund", json={"amount_minor": amount}, headers=h)
    assert done.status_code == 200 and done.json["status"] == "refunded"
    assert c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json["first_payment_due"] is True


def test_a_renewal_can_be_refunded_and_ends_the_paid_time(api: Flask) -> None:
    import uuid

    from app.platform.models import BillingOrder, Square

    c, h, sq, _first = _paid_first(api, "pr3", "grove")
    db = api.extensions["db_factory"]()()
    try:
        row = db.get(Square, uuid.UUID(sq["id"]))
        db.add(BillingOrder(square_id=row.id, kind="running", running_plan="live", interval="month", amount_minor=2_500, status="paid", provider="fake",
                            provider_ref="in_test_1", paid_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1)))  # fmt: skip
        db.commit()
    finally:
        db.close()
    orders = c.get(f"/api/platform/v1/owner/squares/{sq['id']}", headers=h).json["orders"]
    renewal = next(o for o in orders if o["kind"] == "running")
    assert renewal["refundable"] is True
    done = c.post(f"/api/platform/v1/owner/billing/orders/{renewal['id']}/refund", headers=h)
    assert done.status_code == 200 and done.json["status"] == "refunded"
    now = c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json
    assert now["running_plan"] == "keep"  # nothing is paid any more: it sleeps


def test_an_event_pass_refund_ends_the_pass_and_starts_its_archive(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _square(api, "pr4", "event", country="NO")
    co = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "event_pass"}, headers=h).json["order_id"]
    assert c.post(f"/api/platform/v1/billing/orders/{co}/fake-confirm", json={"outcome": "paid"}, headers=h).status_code == 200
    c = as_admin(api, c)
    assert c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json["event_pass"]["phase"] == "live"
    done = c.post(f"/api/platform/v1/owner/billing/orders/{co}/refund", headers=h)
    assert done.status_code == 200 and done.json["status"] == "refunded"
    assert c.get(f"/api/platform/v1/squares/{sq['id']}", headers=h).json["event_pass"]["phase"] == "archive"
    assert c.post(f"/api/platform/v1/owner/billing/orders/{co}/refund", headers=h).status_code == 409  # only once


def test_an_upgrade_and_a_stranger_cannot_be_refunded(api: Flask) -> None:
    c, h, sq, oid = _paid_first(api, "pr5")
    up = c.post(f"/api/platform/v1/squares/{sq['id']}/billing/checkout", json={"kind": "upgrade", "launch_package": "square"}, headers=h)
    if up.status_code == 201:
        assert c.post(f"/api/platform/v1/billing/orders/{up.json['order_id']}/fake-confirm", json={"outcome": "paid"}, headers=h).status_code == 200
        assert c.post(f"/api/platform/v1/owner/billing/orders/{up.json['order_id']}/refund", headers=h).status_code == 409
    assert c.post(f"/api/platform/v1/owner/billing/orders/{uuid_zero()}/refund", headers=h).status_code == 404


def uuid_zero() -> str:
    return "00000000-0000-0000-0000-000000000000"
