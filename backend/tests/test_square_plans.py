# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Launch packages decide which modules an owner may switch on (rootsquares W10-R40, docs/plans/pricing-strategy.md)."""

from flask import Flask

from app.platform import modules as square_modules
from app.platform import plans
from app.platform.reserved_slugs import is_reserved
from tests.staff_client import as_admin
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _login(api: Flask, who: str):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    return c, h


def test_the_rules_of_the_packages() -> None:
    assert plans.allowed_modules("roots") == []
    assert (
        plans.allowed_modules("square") == [k for k in square_modules.KEYS if k in plans.SQUARE_MODULES]
        and "donations" not in plans.allowed_modules("square")
        and "messages" in plans.allowed_modules("square")
    )
    assert plans.allowed_modules("grove") == list(square_modules.KEYS)
    assert plans.allowed_modules(None) == list(square_modules.KEYS)  # a square made before packages: nothing taken away
    assert set(plans.allowed_modules("event")) == {
        "events",
        "payments",
        "tickets",
        "coupons",
        "checkin",
        "members",
        "volunteering",
        "accounting",
        "sponsors",
        "messages",
    }  # ADR 044: no gallery, no memberships
    for package in plans.PACKAGES:  # a package is always closed under what its modules need
        allowed = set(plans.allowed_modules(package))
        assert all(set(square_modules.normalize([k])) <= allowed for k in allowed), package


def test_reserved_names_cannot_be_a_square_address(api: Flask) -> None:
    c, h = _login(api, "rs1")
    for slug in ("admin", "api", "admin-api", "login", "mail", "rootsquares", "squares", "customers"):
        r = c.post(f"{PREFIX}/squares", json={"name": "Impostor", "slug": slug, "theme_id": "paper-brick"}, headers=h)
        assert r.status_code == 409 and r.json["code"] == "slug_reserved", slug
    assert c.post(f"{PREFIX}/squares", json={"name": "Fine Club", "slug": "fine-club", "theme_id": "paper-brick"}, headers=h).status_code == 202
    assert not is_reserved("fine-club") and is_reserved(" Admin ")


def test_the_owner_sets_and_clears_the_squares_mail_contact(api: Flask) -> None:
    c, h = _login(api, "mc1")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Mail Club", "slug": "mail-club", "theme_id": "paper-brick"}, headers=h).json
    assert sq["mail_contact_email"] is None
    url = f"{PREFIX}/squares/{sq['id']}/mail-contact"
    r = c.put(url, json={"email": " Club@Example.ORG "}, headers=h)
    assert r.status_code == 200 and r.json["mail_contact_email"] == "club@example.org"
    assert c.put(url, json={"email": "not an address"}, headers=h).status_code == 422
    assert c.put(url, json={"email": ""}, headers=h).json["mail_contact_email"] is None  # blank clears it
    c.put(url, json={"email": "again@example.org"}, headers=h)
    assert c.put(url, json={"email": None}, headers=h).json["mail_contact_email"] is None
    c2, h2 = _login(api, "mc2")
    assert c2.put(url, json={"email": "thief@example.org"}, headers=h2).status_code in (403, 404)  # not the owner's organisation


def test_a_new_square_starts_with_its_packages_modules(api: Flask) -> None:
    c, h = _login(api, "pk1")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Roots Club", "slug": "roots-club", "theme_id": "paper-brick", "launch_package": "roots"}, headers=h).json
    assert sq["launch_package"] == "roots" and sq["running_plan"] == "live" and sq["modules"] == [] and sq["allowed_modules"] == []
    sq2 = c.post(f"{PREFIX}/squares", json={"name": "Square Club", "slug": "square-club", "theme_id": "paper-brick"}, headers=h).json
    assert (
        sq2["launch_package"] == "square" and sq2["modules"] == plans.starting_modules("square") and set(sq2["modules"]) <= set(plans.allowed_modules("square"))
    )
    sq3 = c.post(f"{PREFIX}/squares", json={"name": "One Event", "slug": "one-event", "theme_id": "paper-brick", "launch_package": "event"}, headers=h).json
    assert sq3["running_plan"] == "event" and set(sq3["modules"]) == set(plans.allowed_modules("event"))
    assert sq3["event_pass"]["phase"] == "live" and sq3["event_pass"]["days_left"] in (44, 45)  # the clock of the pass started


def test_modules_outside_the_package_are_refused(api: Flask) -> None:
    c, h = _login(api, "pk2")
    body = {"name": "Too Much", "slug": "too-much", "theme_id": "paper-brick", "launch_package": "roots", "modules": ["events"]}
    bad = c.post(f"{PREFIX}/squares", json=body, headers=h)
    assert bad.status_code == 422
    sq = c.post(f"{PREFIX}/squares", json={"name": "Square Two", "slug": "square-two", "theme_id": "paper-brick", "launch_package": "square"}, headers=h).json
    no = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["events", "payments", "coupons"]}, headers=h)
    assert no.status_code == 403 and no.json["code"] == "module_not_in_package"
    ok = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["gallery"]}, headers=h)
    assert ok.status_code == 200 and ok.json["modules"] == ["gallery"]
    news = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["news"]}, headers=h)  # News is Grove (W15-R23)
    assert news.status_code == 403 and news.json["code"] == "module_not_in_package"


def test_owners_cannot_change_their_own_package(api: Flask) -> None:
    c, h = _login(api, "pk3")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Stuck", "slug": "stuck-sq", "theme_id": "paper-brick", "launch_package": "roots"}, headers=h).json
    assert c.put(f"{PREFIX}/squares/{sq['id']}/plan", json={"launch_package": "grove"}, headers=h).status_code == 403


def test_a_platform_admin_can_change_the_plan_and_modules_stay_on(api: Flask) -> None:
    c, h = _login(api, "pk4")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Grows", "slug": "grows-sq", "theme_id": "paper-brick", "launch_package": "square"}, headers=h).json
    c = as_admin(api, c)
    up = c.put(f"{PREFIX}/squares/{sq['id']}/plan", json={"launch_package": "grove", "running_plan": "keep"}, headers=h)
    assert up.status_code == 200 and up.json["launch_package"] == "grove" and up.json["running_plan"] == "keep"
    assert up.json["modules"] == sq["modules"] and up.json["allowed_modules"] == list(square_modules.KEYS)
    assert c.put(f"{PREFIX}/squares/{sq['id']}/plan", json={"launch_package": "nope"}, headers=h).status_code == 422


def test_the_owner_puts_the_square_to_sleep_and_wakes_it(api: Flask) -> None:
    c, h = _login(api, "pk5")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Naps", "slug": "naps-sq", "theme_id": "paper-brick"}, headers=h).json
    asleep = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
    assert asleep.status_code == 200 and asleep.json["running_plan"] == "keep" and asleep.json["modules"] == sq["modules"]
    assert c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "live"}, headers=h).json["running_plan"] == "live"
    assert c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "event"}, headers=h).status_code == 422


def test_an_event_pass_stays_an_event_pass(api: Flask) -> None:
    c, h = _login(api, "pk6")
    sq = c.post(f"{PREFIX}/squares", json={"name": "Once", "slug": "once-sq", "theme_id": "paper-brick", "launch_package": "event"}, headers=h).json
    assert c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h).status_code == 409
