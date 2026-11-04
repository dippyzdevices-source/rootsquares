# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Several codes on one payment (W15-R19): how they combine is a platform setting; by default the best code wins and the rest are ignored."""

from flask import Flask

from tests.billing.helpers import PREFIX, _checkout, _square, api  # noqa: F401
from tests.staff_client import as_admin

CHECK = "voucher-check"


def _admin(api: Flask, who: str):
    c, h, sq = _square(api, who, "roots")
    c = as_admin(api, c)
    return c, h, sq


def _voucher(c, h, **body):
    return c.post(f"{PREFIX}/vouchers", json=body, headers=h)


def _check(c, h, sq, code):
    return c.post(f"{PREFIX}/squares/{sq['id']}/billing/{CHECK}", json={"code": code, "kind": "first", "interval": "month"}, headers=h).json


def _mode(c, h, mode, max_codes=2):
    return c.put(f"{PREFIX}/voucher-settings", json={"mode": mode, "max_codes": max_codes}, headers=h)


def test_the_default_is_that_the_best_of_two_codes_wins_and_the_other_is_ignored(api: Flask) -> None:
    c, h, sq = _admin(api, "st1")
    assert c.get(f"{PREFIX}/voucher-settings", headers=h).json == {"mode": "best", "max_codes": 2}
    _voucher(c, h, code="TWENTY", kind="percent", value=20)
    _voucher(c, h, code="FIVE", kind="fixed", value=500)
    out = _check(c, h, sq, "five twenty")
    assert out["valid"] and out["codes"] == ["TWENTY"] and out["discount_minor"] == 2_980  # 20 % of the $149 package
    assert out["ignored"] == [{"code": "FIVE", "why": "Not used: another code takes more off."}]
    co = _checkout(c, h, sq, kind="first", interval="month", voucher_code="FIVE, TWENTY").json["order_id"]
    order = c.get(f"{PREFIX}/billing/orders/{co}", headers=h).json
    assert order["voucher_code"] == "TWENTY" and order["discount_minor"] == 2_980
    assert _check(c, h, sq, "A B C")["reason"] == "voucher_too_many"  # at most two by default


def test_only_a_platform_admin_changes_how_codes_combine_and_bad_settings_are_refused(api: Flask) -> None:
    c, h, _ = _square(api, "st2", "roots")
    assert _mode(c, h, "sequential").status_code == 404
    c = as_admin(api, c)
    assert _mode(c, h, "sequential", 3).status_code == 200
    assert c.get(f"{PREFIX}/voucher-settings", headers=h).json == {"mode": "sequential", "max_codes": 3}
    assert _mode(c, h, "wild").status_code == 422
    assert _mode(c, h, "best", 6).status_code == 422
    assert _mode(c, h, "best", 0).status_code == 422


def test_stacking_needs_both_codes_marked_can_be_combined_and_applies_one_after_the_other(api: Flask) -> None:
    c, h, sq = _admin(api, "st3")
    _voucher(c, h, code="TWENTY", kind="percent", value=20, stackable=True)
    _voucher(c, h, code="TEN", kind="percent", value=10, stackable=True)
    _voucher(c, h, code="SOLO", kind="fixed", value=300)
    _mode(c, h, "sequential")
    assert _check(c, h, sq, "TWENTY SOLO")["reason"] == "voucher_not_stackable"
    out = _check(c, h, sq, "TWENTY TEN")
    # $149 package: 20 % = 2980, then 10 % of what is left (11920) = 1192; the $25 Live month stays whole
    assert out["discount_minor"] == 2_980 + 1_192 and out["payable_minor"] == 17_400 - 4_172 and out["codes"] == ["TWENTY", "TEN"] and out["ignored"] == []
    co = _checkout(c, h, sq, kind="first", interval="month", voucher_code="TWENTY TEN").json["order_id"]
    order = c.get(f"{PREFIX}/billing/orders/{co}", headers=h).json
    assert order["voucher_code"] == "TWENTY TEN" and order["amount_minor"] == 17_400 - 4_172
    c.post(f"{PREFIX}/billing/orders/{co}/fake-confirm", json={"outcome": "paid"}, headers=h)
    items = {v["code"]: v for v in c.get(f"{PREFIX}/vouchers", headers=h).json["items"]}
    assert (items["TWENTY"]["uses"], items["TWENTY"]["discount_minor"]) == (1, 2_980)  # each voucher counts its own share
    assert (items["TEN"]["uses"], items["TEN"]["discount_minor"]) == (1, 1_192)
    assert items["SOLO"]["uses"] == 0


def test_additive_codes_add_up_on_the_same_price_and_a_partner_code_is_the_main_one(api: Flask) -> None:
    c, h, sq = _admin(api, "st4")
    partner = c.post(f"{PREFIX}/partners", json={"name": "Aino", "email": "aino@example.com", "commission_percent": 10}, headers=h).json
    _voucher(c, h, code="PLAIN", kind="percent", value=20, stackable=True)
    _voucher(c, h, code="AINO10", kind="percent", value=10, stackable=True, partner_id=partner["id"])
    _mode(c, h, "additive")
    out = _check(c, h, sq, "PLAIN AINO10")
    assert out["discount_minor"] == 2_980 + 1_490  # 20 % + 10 % of the same $149
    co = _checkout(c, h, sq, kind="first", interval="month", voucher_code="PLAIN AINO10").json["order_id"]
    c.post(f"{PREFIX}/billing/orders/{co}/fake-confirm", json={"outcome": "paid"}, headers=h)
    report = c.get(f"{PREFIX}/partners/{partner['id']}/report", headers=h).json
    assert report["uses"] == 1  # the partner's code was on the order, so the partner is credited
    plain_lines = c.get(f"{PREFIX}/vouchers", headers=h).json["items"]
    assert {v["code"]: v["uses"] for v in plain_lines} == {"PLAIN": 1, "AINO10": 1}


def test_a_percentage_pair_never_takes_more_than_the_package_and_a_code_with_nothing_left_is_ignored(api: Flask) -> None:
    c, h, sq = _admin(api, "st5")
    _voucher(c, h, code="ALL", kind="percent", value=100, stackable=True)
    _voucher(c, h, code="MORE", kind="percent", value=50, stackable=True)
    _mode(c, h, "sequential")
    out = _check(c, h, sq, "ALL MORE")
    assert out["discount_minor"] == 14_900 and out["payable_minor"] == 2_500  # the Live month is never lowered
    assert out["codes"] == ["ALL"] and out["ignored"][0]["code"] == "MORE"
