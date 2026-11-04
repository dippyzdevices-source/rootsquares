# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Vouchers and partners (W14-R27): a code lowers a launch package or an Event pass once; a use is a paid order."""

from flask import Flask

from tests.billing.helpers import PREFIX, _checkout, _square, api  # noqa: F401
from tests.staff_client import as_admin


def _admin(api: Flask, who: str, package: str = "roots", country: str | None = None):
    c, h, sq = _square(api, who, package, country)
    c = as_admin(api, c)
    return c, h, sq


def _voucher(c, h, **body):
    base = {"code": "WELCOME20", "kind": "percent", "value": 20}
    return c.post(f"{PREFIX}/vouchers", json={**base, **body}, headers=h)


def _pay(c, h, order_id, outcome="paid"):
    return c.post(f"{PREFIX}/billing/orders/{order_id}/fake-confirm", json={"outcome": outcome}, headers=h)


def test_only_a_platform_admin_makes_vouchers_and_a_bad_one_is_refused(api: Flask) -> None:
    c, h, _ = _square(api, "vc1")
    assert _voucher(c, h).status_code == 404
    c = as_admin(api, c)
    made = _voucher(c, h, code=" welcome 20 ")
    assert made.status_code == 201 and made.json["code"] == "WELCOME20" and made.json["uses"] == 0
    assert _voucher(c, h).status_code == 409  # the code exists
    assert _voucher(c, h, code="no").status_code == 422  # too short
    assert _voucher(c, h, code="OVER", value=150).status_code == 422  # a percentage is 1 to 100
    assert _voucher(c, h, code="PKG", packages=["gold"]).status_code == 422
    assert _voucher(c, h, code="DATES", valid_from="2026-02-01T00:00:00Z", valid_until="2026-01-01T00:00:00Z").status_code == 422
    assert c.get(f"{PREFIX}/vouchers", headers=h).json["items"][0]["code"] == "WELCOME20"


def test_a_percentage_lowers_the_package_part_of_the_first_payment_and_not_the_live_period(api: Flask) -> None:
    c, h, sq = _admin(api, "vc2")
    _voucher(c, h)
    co = _checkout(c, h, sq, kind="first", interval="year", voucher_code="welcome20")
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    # package $149 x 20 % = $29.80 off; the Live year ($250) stays whole
    assert order["list_minor"] == 14_900 + 25_000 and order["discount_minor"] == 2_980 and order["amount_minor"] == 14_900 + 25_000 - 2_980
    assert order["voucher_code"] == "WELCOME20"


def test_a_fixed_amount_never_goes_below_the_part_it_lowers(api: Flask) -> None:
    c, h, sq = _admin(api, "vc3")
    _voucher(c, h, code="BIGGIFT", kind="fixed", value=50_000)
    order = c.get(f"{PREFIX}/billing/orders/{_checkout(c, h, sq, kind='first', interval='month', voucher_code='BIGGIFT').json['order_id']}", headers=h).json
    assert order["discount_minor"] == 14_900 and order["amount_minor"] == 2_500  # the whole package, never the Live month


def test_the_owner_sees_the_price_before_paying_and_a_bad_code_says_why(api: Flask) -> None:
    c, h, sq = _admin(api, "vc4")
    _voucher(c, h, code="GROVEONLY", packages=["grove"])
    _voucher(c, h, code="OFF10", kind="fixed", value=1_000, active=False)
    url = f"{PREFIX}/squares/{sq['id']}/billing/voucher-check"
    ok = c.post(url, json={"code": "WELCOME", "kind": "first", "interval": "month"}, headers=h).json
    assert ok == {
        "valid": False,
        "reason": "voucher_unknown",
        "message": "This code is not valid.",
        "list_minor": 0,
        "discount_minor": 0,
        "payable_minor": 0,
        "codes": [],
        "ignored": [],
    }
    _voucher(c, h)
    good = c.post(url, json={"code": "welcome20", "kind": "first", "interval": "month"}, headers=h).json
    assert good["valid"] and good["list_minor"] == 17_400 and good["discount_minor"] == 2_980 and good["payable_minor"] == 14_420
    assert (
        c.post(url, json={"code": "GROVEONLY", "kind": "first", "interval": "month"}, headers=h).json["reason"] == "voucher_not_for_this"
    )  # a Roots square, a Grove code
    assert c.post(url, json={"code": "OFF10", "kind": "first", "interval": "month"}, headers=h).json["reason"] == "voucher_inactive"
    assert (
        c.post(url, json={"code": "WELCOME20", "kind": "running", "running_plan": "live", "interval": "month"}, headers=h).json["reason"]
        == "voucher_not_for_running"
    )
    from sqlalchemy import select

    from app.platform.models import BillingOrder

    db = api.extensions["db_factory"]()()
    assert db.scalar(select(BillingOrder.id)) is None  # checking made and kept nothing
    db.close()


def test_a_use_is_a_paid_order_and_the_limits_follow(api: Flask) -> None:
    c, h, sq = _admin(api, "vc5")
    _voucher(c, h, code="ONCE", max_uses=1)
    first = _checkout(c, h, sq, kind="first", interval="month", voucher_code="ONCE").json["order_id"]
    _pay(c, h, first, "cancelled")
    assert c.get(f"{PREFIX}/vouchers", headers=h).json["items"][0]["uses"] == 0  # a cancelled order is not a use
    again = _checkout(c, h, sq, kind="first", interval="month", voucher_code="ONCE").json["order_id"]
    assert _pay(c, h, again).json["status"] == "paid"
    item = c.get(f"{PREFIX}/vouchers", headers=h).json["items"][0]
    assert item["uses"] == 1 and item["discount_minor"] == 2_980
    red = c.get(f"{PREFIX}/vouchers/{item['id']}/redemptions", headers=h).json["items"]
    assert len(red) == 1 and red[0]["discount_minor"] == 2_980 and red[0]["organization_name"] == "Club vc5"
    c2, h2, sq2 = _square(api, "vc6")  # another customer: the code is used up
    over = _checkout(c2, h2, sq2, kind="first", interval="month", voucher_code="ONCE")
    assert over.status_code == 409 and over.json["code"] == "voucher_used_up"


def test_one_use_per_organisation_and_new_customers_only(api: Flask) -> None:
    c, h, sq = _admin(api, "vc7", "square")
    _voucher(c, h, code="PERORG", max_uses=5)
    _voucher(c, h, code="NEWONLY", new_customers_only=True, once_per_org=False)
    paid = _checkout(c, h, sq, kind="first", interval="month", voucher_code="PERORG").json["order_id"]
    _pay(c, h, paid)
    sq_now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    refused = _checkout(c, h, sq_now, kind="upgrade", launch_package="grove", voucher_code="PERORG")
    assert refused.status_code == 409 and refused.json["code"] == "voucher_already_used"
    old = _checkout(c, h, sq_now, kind="upgrade", launch_package="grove", voucher_code="NEWONLY")
    assert old.status_code == 409 and old.json["code"] == "voucher_new_customers_only"  # this organisation has paid already


def test_a_free_event_pass_is_settled_without_a_card(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _admin(api, "vc8", "event", "NO")
    _voucher(c, h, code="FREEPASS", value=100, applies_to="event_pass")
    ex = api.extensions["executor"]
    assert sq["awaiting_payment"] is True and ex.jobs == []
    co = _checkout(c, h, sq, kind="event_pass", voucher_code="FREEPASS")
    assert co.status_code == 201
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 0 and order["list_minor"] == 2_500 and order["discount_minor"] == 2_500 and order["status"] == "paid"
    assert len(ex.jobs) == 1  # built and started, as when paid
    now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert now["awaiting_payment"] is False and now["event_pass"]["phase"] == "live"


def test_a_launch_voucher_is_not_for_an_event_pass_and_the_package_list_limits_it(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _admin(api, "vc9", "event", "NO")
    _voucher(c, h, code="LAUNCHONLY", applies_to="launch")
    refused = _checkout(c, h, sq, kind="event_pass", voucher_code="LAUNCHONLY")
    assert refused.status_code == 409 and refused.json["code"] == "voucher_not_for_this"


def test_the_partner_report_shows_uses_revenue_discount_and_the_commission_owed(api: Flask) -> None:
    c, h, sq = _admin(api, "vc10")
    partner = c.post(f"{PREFIX}/partners", json={"name": "Local Samaj Network", "email": "p@example.org", "commission_percent": 10}, headers=h)
    assert partner.status_code == 201
    pid = partner.json["id"]
    _voucher(c, h, code="SAMAJ15", value=15, partner_id=pid)
    order = _checkout(c, h, sq, kind="first", interval="month", voucher_code="SAMAJ15").json["order_id"]
    _pay(c, h, order)
    report = c.get(f"{PREFIX}/partners/{pid}/report", headers=h).json
    discount = (14_900 * 15 + 50) // 100
    revenue = 14_900 + 2_500 - discount
    assert (
        report["uses"] == 1
        and report["discount_minor"] == discount
        and report["revenue_minor"] == revenue
        and report["commission_minor"] == revenue * 10 // 100
    )
    assert report["lines"][0]["code"] == "SAMAJ15" and report["partner"]["vouchers"] == 1
    assert c.patch(f"{PREFIX}/partners/{pid}", json={"commission_percent": 20}, headers=h).json["commission_percent"] == 20
    assert _voucher(c, h, code="NOPARTNER", partner_id="00000000-0000-0000-0000-000000000000").status_code == 422


def test_a_used_code_cannot_be_renamed_but_can_be_switched_off(api: Flask) -> None:
    c, h, sq = _admin(api, "vc11")
    vid = _voucher(c, h).json["id"]
    _pay(c, h, _checkout(c, h, sq, kind="first", interval="month", voucher_code="WELCOME20").json["order_id"])
    assert c.patch(f"{PREFIX}/vouchers/{vid}", json={"code": "RENAMED"}, headers=h).status_code == 409
    off = c.patch(f"{PREFIX}/vouchers/{vid}", json={"active": False, "clear": ["max_uses"]}, headers=h)
    assert off.status_code == 200 and off.json["active"] is False


def test_a_code_given_when_the_square_is_created_is_kept_and_lowers_the_first_payment(api: Flask) -> None:
    c, h, _ = _admin(api, "vc12")
    _voucher(c, h, code="AT-START")
    body = {"name": "Second", "slug": "sq-vc12-b", "theme_id": "paper-brick", "launch_package": "square", "voucher_code": "at-start"}
    made = c.post(f"{PREFIX}/squares", json=body, headers=h)
    assert made.status_code == 202 and made.json["voucher_code"] == "AT-START"
    order = c.get(
        f"{PREFIX}/billing/orders/{_checkout(c, h, made.json, kind='first', interval='month').json['order_id']}", headers=h
    ).json  # nothing typed: the kept code is used
    assert order["voucher_code"] == "AT-START" and order["discount_minor"] == (29_900 * 20 + 50) // 100 and order["list_minor"] == 29_900 + 2_500
    bad = c.post(f"{PREFIX}/squares", json={**body, "slug": "sq-vc12-c", "voucher_code": "NOPE"}, headers=h)
    assert bad.status_code == 409 and bad.json["code"] == "voucher_unknown"
    assert c.get(f"{PREFIX}/squares", headers=h).json is not None  # the refused square was not made


def test_the_create_square_page_can_price_a_code_before_the_square_exists(api: Flask) -> None:
    c, h, _ = _admin(api, "vc13")
    _voucher(c, h, code="PREVIEW10", value=10)
    url = f"{PREFIX}/billing/voucher-preview"
    ok = c.post(url, json={"code": "preview10", "kind": "first", "launch_package": "grove"}, headers=h).json
    assert ok["valid"] and ok["discount_minor"] == (39_900 * 10 + 50) // 100 and ok["payable_minor"] == 39_900 + 2_500 - ok["discount_minor"]
    event = c.post(url, json={"code": "PREVIEW10", "kind": "event_pass"}, headers=h).json
    assert event["valid"] and event["list_minor"] == 2_500
    assert c.post(url, json={"code": "NOPE", "kind": "first", "launch_package": "roots"}, headers=h).json["reason"] == "voucher_unknown"
    assert c.post(url, json={"code": "PREVIEW10", "kind": "running"}, headers=h).status_code == 422
