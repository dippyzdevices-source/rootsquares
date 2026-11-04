# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The owner console Subscriptions numbers."""

import datetime as dt

from flask import Flask
from sqlalchemy import select

from app.platform.models import Square
from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401
from tests.staff_client import as_admin


def test_the_subscriptions_overview_counts_states_and_money(api: Flask) -> None:
    from app.platform import subscriptions

    _square(api, "sb1", "roots")  # on trial
    _square(api, "sb2", "square")  # renewing
    _square(api, "sb3", "event")  # the Event pass is not a subscription
    db = api.extensions["db_factory"]()()
    try:
        # the order and the subscription of sb2 are written directly
        from app.platform.models import BillingOrder

        row = db.scalar(select(Square).where(Square.slug == "sq-sb2"))
        order = BillingOrder(
            square_id=row.id, kind="first", launch_package="square", running_plan="live", interval="month", amount_minor=32_400, status="paid",
            provider="stripe", paid_at=NOW,
        )  # fmt: skip
        db.add(order)
        row.stripe_subscription_id = "sub_x"
        row.paid_until = NOW + dt.timedelta(days=30)
        db.commit()
        out = subscriptions.overview(db, now=NOW)
    finally:
        db.close()
    assert out["mrr_minor"] == 2_500 and out["paying"] == 1 and out["trial"] == 1 and out["failed"] == 0 and out["paid_30d_minor"] == 32_400
    by = {p["key"]: p["count"] for p in out["packages"]}
    assert by == {"roots": 1, "square": 1, "grove": 0, "event": 1}
    states = {u["slug"]: u["state"] for u in out["upcoming"]}
    assert states["sq-sb2"] == "renewing" and states["sq-sb1"] == "trial" and "sq-sb3" not in states


def test_the_subscriptions_route_is_for_admins(api: Flask) -> None:
    c, h, _ = _square(api, "sb4", "roots")
    assert c.get("/api/platform/v1/owner/subscriptions", headers=h).status_code == 404
    c = as_admin(api, c)
    got = c.get("/api/platform/v1/owner/subscriptions", headers=h)
    assert got.status_code == 200 and got.json["trial"] == 1 and len(got.json["packages"]) == 4
