# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The 7-day trial and the first payment (launch package plus first Live period)."""

import datetime as dt

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_a_new_square_starts_with_seven_free_days_of_live_and_an_event_pass_has_none(api: Flask) -> None:
    c, h, sq = _square(api, "bl9", "roots")
    left = dt.datetime.fromisoformat(sq["paid_until"]).replace(tzinfo=None) - dt.datetime.now(dt.UTC).replace(tzinfo=None)  # sqlite gives times without a zone
    assert dt.timedelta(days=6, hours=23) < left < dt.timedelta(days=7, hours=1)
    _, _, ev = _square(api, "bl10", "event")
    assert ev["paid_until"] is None


def test_the_first_payment_is_the_package_plus_the_first_live_period(api: Flask) -> None:
    c, h, sq = _square(api, "bl14", "roots")
    assert sq["first_payment_due"] is True
    co = _checkout(c, h, sq, kind="first", interval="year")
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 14_900 + 25_000 and order["kind"] == "first"
    assert _checkout(c, h, sq, kind="first", interval="week").status_code == 400
    c.post(f"{PREFIX}/billing/orders/{order['id']}/fake-confirm", json={"outcome": "paid"}, headers=h)
    now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert now["first_payment_due"] is False and now["launch_package"] == "roots"
    left = dt.datetime.fromisoformat(now["paid_until"]).replace(tzinfo=None) - dt.datetime.now(dt.UTC).replace(tzinfo=None)
    assert left > dt.timedelta(days=370)  # the 7 trial days plus the paid year
    assert _checkout(c, h, now, kind="first", interval="month").status_code == 409
    ev = _square(api, "bl15", "event")
    assert ev[2]["first_payment_due"] is False


def test_with_money_on_the_first_payment_comes_before_upgrades_and_running_periods(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _square(api, "fp1", "roots", country="NO")
    assert sq["payment_required"] is True and sq["first_payment_due"] is True
    for body in ({"kind": "upgrade", "launch_package": "grove"}, {"kind": "running", "running_plan": "live", "interval": "month"}):
        r = _checkout(c, h, sq, **body)
        assert r.status_code == 409 and r.json["code"] == "first_payment_due"
    assert _checkout(c, h, sq, kind="first", interval="month", launch_package="nope").status_code == 400
    # a higher package is paid in full and replaces the starting one
    co = _checkout(c, h, sq, kind="first", interval="month", launch_package="grove")
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 39_900 + 2_500 and order["launch_package"] == "grove"
    c.post(f"{PREFIX}/billing/orders/{order['id']}/fake-confirm", json={"outcome": "paid"}, headers=h)
    now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert now["launch_package"] == "grove" and now["first_payment_due"] is False
    assert _checkout(c, h, now, kind="running", running_plan="live", interval="month").status_code == 201  # after the first payment it is allowed


def test_a_lower_package_than_the_starting_one_is_refused_at_the_first_payment(api: Flask) -> None:
    c, h, sq = _square(api, "fp2", "grove")
    assert _checkout(c, h, sq, kind="first", interval="month", launch_package="roots").status_code == 400
