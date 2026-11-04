# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Orders: package upgrades, running periods, cancel, who may pay, the default billing period, the fake provider."""

import datetime as dt

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_an_upgrade_costs_the_difference_and_applies_only_when_paid(api: Flask) -> None:
    c, h, sq = _square(api, "bl2", "roots")
    co = _checkout(c, h, sq, kind="upgrade", launch_package="grove")
    assert co.status_code == 201 and "/billing/checkout?order=" in co.json["url"]
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 39_900 - 14_900 and order["status"] == "pending" and order["currency"] == "USD"
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["launch_package"] == "roots"  # nothing changes before payment
    paid = c.post(f"{PREFIX}/billing/orders/{order['id']}/fake-confirm", json={"outcome": "paid"}, headers=h)
    assert paid.status_code == 200 and paid.json["status"] == "paid"
    now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert now["launch_package"] == "grove" and len(now["allowed_modules"]) > 0
    again = c.post(f"{PREFIX}/billing/orders/{order['id']}/fake-confirm", json={"outcome": "cancelled"}, headers=h)
    assert again.json["status"] == "paid"  # a paid order never turns back (providers retry)
    assert [o["status"] for o in c.get(f"{PREFIX}/squares/{sq['id']}/billing/orders", headers=h).json["items"]] == ["paid"]


def test_a_cancelled_checkout_changes_nothing(api: Flask) -> None:
    c, h, sq = _square(api, "bl3", "roots")
    oid = _checkout(c, h, sq, kind="upgrade", launch_package="square").json["order_id"]
    assert c.post(f"{PREFIX}/billing/orders/{oid}/fake-confirm", json={"outcome": "cancelled"}, headers=h).json["status"] == "cancelled"
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["launch_package"] == "roots"


def test_there_is_nothing_to_upgrade_to_from_the_top_or_sideways(api: Flask) -> None:
    c, h, sq = _square(api, "bl4", "grove")
    for target in ("grove", "roots", "event"):
        r = _checkout(c, h, sq, kind="upgrade", launch_package=target)
        assert r.status_code == 409 and r.json["code"] == "no_upgrade", target
    assert _checkout(c, h, sq, kind="upgrade", launch_package="nope").status_code == 422


def test_a_running_period_sets_paid_until_and_adds_when_paid_early(api: Flask) -> None:
    c, h, sq = _square(api, "bl5", "square")
    ids = [_checkout(c, h, sq, kind="running", running_plan="live", interval=i).json["order_id"] for i in ("month", "year")]
    first = c.post(f"{PREFIX}/billing/orders/{ids[0]}/fake-confirm", json={"outcome": "paid"}, headers=h).json
    assert first["amount_minor"] == 2_500 and first["interval"] == "month"
    t1 = dt.datetime.fromisoformat(c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["paid_until"])
    c.post(f"{PREFIX}/billing/orders/{ids[1]}/fake-confirm", json={"outcome": "paid"}, headers=h)
    t2 = dt.datetime.fromisoformat(c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["paid_until"])
    assert dt.timedelta(days=364) < t2 - t1 < dt.timedelta(days=366)  # the year was added to the month that was left
    bad = _checkout(c, h, sq, kind="running", running_plan="event", interval="month")
    assert bad.status_code == 400 and bad.json["code"] == "bad_plan"


def test_an_event_pass_has_no_running_period_to_buy(api: Flask) -> None:
    c, h, sq = _square(api, "bl6", "event")
    r = _checkout(c, h, sq, kind="running", running_plan="live", interval="month")
    assert r.status_code == 409 and r.json["code"] == "event_pass"


def test_somebody_else_cannot_pay_or_look(api: Flask) -> None:
    c, h, sq = _square(api, "bl7", "roots")
    oid = _checkout(c, h, sq, kind="upgrade", launch_package="square").json["order_id"]
    other = {**HEADERS, "Authorization": "Bearer fake:u-bl8:bl8@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert _checkout(c, other, sq, kind="upgrade", launch_package="grove").status_code == 404
    assert c.get(f"{PREFIX}/billing/orders/{oid}", headers=other).status_code == 404
    assert c.post(f"{PREFIX}/billing/orders/{oid}/fake-confirm", json={"outcome": "paid"}, headers=other).status_code == 404
    assert c.get(f"{PREFIX}/squares/{sq['id']}/billing/orders", headers=other).status_code == 404


def test_the_fake_provider_has_no_webhook(api: Flask) -> None:
    assert api.test_client().post(f"{PREFIX}/billing/webhook", data=b"{}").status_code == 501  # the Stripe adapter is tested in test_stripe_adapter.py


def test_the_owner_sets_a_default_billing_period(api: Flask) -> None:
    c, h, sq = _square(api, "bl11", "square")
    assert sq["billing_interval"] == "month"
    out = c.put(f"{PREFIX}/squares/{sq['id']}/billing-interval", json={"interval": "year"}, headers=h)
    assert out.status_code == 200 and out.json["billing_interval"] == "year"
    assert c.put(f"{PREFIX}/squares/{sq['id']}/billing-interval", json={"interval": "week"}, headers=h).status_code == 422
    other = {**HEADERS, "Authorization": "Bearer fake:u-bl12:bl12@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.put(f"{PREFIX}/squares/{sq['id']}/billing-interval", json={"interval": "year"}, headers=other).status_code == 404
