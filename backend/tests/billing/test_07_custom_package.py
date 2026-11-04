# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The custom package (W19-R20, ADR 082): an admin agrees modules and one amount per period with a square; other packages are unchanged."""

from flask import Flask

from tests.billing.helpers import PREFIX, _checkout, _square, api  # noqa: F401
from tests.staff_client import as_admin

AGREED = {"modules": ["events", "payments", "tickets", "gallery"], "amount_minor": 7_500, "interval": "month"}


def _admin(api: Flask, who: str):
    c, h, sq = _square(api, who, "roots")
    c = as_admin(api, c)
    return c, h, sq


def test_only_a_platform_admin_sets_a_custom_package(api: Flask) -> None:
    c, h, sq = _square(api, "cu1", "roots")
    assert c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json=AGREED, headers=h).status_code == 403


def test_the_custom_package_has_exactly_the_agreed_modules_and_price(api: Flask) -> None:
    c, h, sq = _admin(api, "cu2")
    r = c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json=AGREED, headers=h)
    assert r.status_code == 200
    assert r.json["launch_package"] == "custom" and r.json["custom_amount_minor"] == 7_500 and r.json["custom_interval"] == "month"
    assert {"events", "payments", "tickets", "gallery"} <= set(r.json["allowed_modules"]) and "donations" not in r.json["allowed_modules"]
    bad = c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json={**AGREED, "modules": ["events", "nope"]}, headers=h)
    assert bad.status_code == 422
    assert c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json={**AGREED, "amount_minor": 0}, headers=h).status_code == 422
    assert c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json={**AGREED, "interval": "week"}, headers=h).status_code == 422


def test_a_custom_square_pays_the_agreed_amount_whatever_the_page_asks(api: Flask) -> None:
    c, h, sq = _admin(api, "cu3")
    c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json={**AGREED, "interval": "year", "amount_minor": 80_000}, headers=h)
    co = _checkout(c, h, sq, kind="running", running_plan="keep", interval="month")
    assert co.status_code == 201
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 80_000 and order["running_plan"] == "live" and order["interval"] == "year"


def test_a_custom_square_cannot_change_plan_or_sleep(api: Flask) -> None:
    c, h, sq = _admin(api, "cu4")
    c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json=AGREED, headers=h)
    keep = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
    assert keep.status_code == 409 and keep.json.get("code") == "custom_package"
    change = c.post(f"{PREFIX}/squares/{sq['id']}/billing/plan-change", json={"plan": "keep"}, headers=h)
    assert change.status_code == 409 and change.json.get("code") == "custom_package"


def test_the_owner_cannot_switch_on_a_module_outside_the_agreement(api: Flask) -> None:
    c, owner_h, sq = _square(api, "cu5", "roots")
    ac, _, _ = _admin(api, "cu5a")
    assert ac.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json=AGREED).status_code == 200
    inside = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["events", "payments", "tickets"]}, headers=owner_h)
    assert inside.status_code == 200
    outside = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["events", "donations"]}, headers=owner_h)
    assert outside.status_code in (402, 403, 409, 422)
    from app.platform import plans

    assert plans.outside_package("custom", ["events", "donations"], '["events", "payments"]') == ["donations"]


def test_the_event_pass_is_never_a_custom_package(api: Flask) -> None:
    c, h, sq = _admin(api, "cu6")
    c.put(f"{PREFIX}/squares/{sq['id']}/plan", json={"launch_package": "event", "running_plan": "event"}, headers=h)
    r = c.put(f"{PREFIX}/squares/{sq['id']}/custom-package", json=AGREED, headers=h)
    assert r.status_code == 409 and r.json.get("code") == "event_pass"


def test_core_parts_follow_their_hierarchy_and_old_lists_keep_all():
    from app.platform import modules as m
    from app.platform import plans as p

    assert m.normalize_core(["settings"]) == ["login", "admin", "settings"]  # settings needs admin, admin needs login
    assert m.normalize_core(["home", "about"]) == ["home", "about"]  # a two-page site needs nothing else
    assert m.normalize_core([], ["tickets"]) == ["login", "account", "admin"]  # a module brings the parts it is run from
    assert p.custom_core_of('["events","payments"]') == list(m.CORE_KEYS)  # a list saved before: all parts stay
    assert p.custom_core_of('["home","about"]') == ["home", "about"]


def test_the_guide_amounts_are_set_by_a_platform_admin_only(api: Flask) -> None:
    c, h, _sq = _square(api, "cu9", "roots")
    assert c.get(f"{PREFIX}/custom-guide", headers=h).status_code == 404
    assert c.put(f"{PREFIX}/custom-guide", json={"steps": [0, 5_000, 0, 0, 0]}, headers=h).status_code == 404
    c = as_admin(api, c)
    assert c.get(f"{PREFIX}/custom-guide", headers=h).json["steps"] == [0, 0, 0, 0, 0]
    ok = c.put(f"{PREFIX}/custom-guide", json={"steps": [0, 5_000, 9_000, 12_000, 20_000]}, headers=h)
    assert ok.status_code == 200 and ok.json["steps"] == [0, 5_000, 9_000, 12_000, 20_000]
    assert c.get(f"{PREFIX}/custom-guide", headers=h).json["steps"][1] == 5_000
    assert c.put(f"{PREFIX}/custom-guide", json={"steps": [1, 2, 3]}, headers=h).status_code == 422
    assert c.put(f"{PREFIX}/custom-guide", json={"steps": [-1, 0, 0, 0, 0]}, headers=h).status_code == 422
