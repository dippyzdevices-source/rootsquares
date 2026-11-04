# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Starter sets: the kind of group decides what a new square starts with (rootsquares W14-R10, ADR 064)."""

from flask import Flask

from app.platform import modules as square_modules
from app.platform import plans, starter_sets
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _login(api: Flask, who: str):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    return c, h


def _create(c, h, slug: str, **extra):
    return c.post(f"{PREFIX}/squares", json={"name": f"Club {slug}", "slug": slug, "theme_id": "paper-brick", **extra}, headers=h)


def test_every_set_uses_real_modules_and_is_closed_under_what_they_need() -> None:
    assert starter_sets.KEYS == ("cultural", "religious", "band", "charity")
    for s in starter_sets.STARTER_SETS:
        assert not square_modules.unknown_keys(list(s.modules)), s.key
        assert starter_sets.starter_modules(s.key) == square_modules.normalize(list(s.modules)), s.key
        assert set(starter_sets.starter_modules(s.key)) <= set(plans.allowed_modules("grove")), s.key


def test_cultural_is_what_every_square_started_with_and_religious_leaves_out_tickets_and_memberships() -> None:
    cultural = {"events", "tickets", "coupons", "checkin", "payments", "members", "messages", "gallery", "committee", "news", "accounting"}
    assert set(starter_sets.starter_modules("cultural")) == cultural  # the Recommended group of a cultural group (W15-R27)
    assert starter_sets.starter_modules(None) == starter_sets.starter_modules("cultural")  # a square made before starter sets
    religious = set(starter_sets.starter_modules("religious"))
    assert {"events", "members", "payments", "donations", "messages"} <= religious
    assert not religious & {"tickets", "memberships", "coupons", "checkin"}


def test_bands_sell_tickets_and_charities_take_donations() -> None:
    band = set(starter_sets.starter_modules("band"))
    assert {"events", "tickets", "payments", "newsletter", "messages", "sponsors", "testimonials"} <= band
    assert "members" not in band
    charity = set(starter_sets.starter_modules("charity"))
    assert {"donations", "payments", "newsletter", "messages", "accounting", "sponsors"} <= charity
    assert not charity & {"tickets", "memberships", "coupons", "checkin"}


def test_a_package_limits_what_starts_on() -> None:
    assert plans.starting_modules("roots", "religious") == []
    assert set(plans.starting_modules("square", "religious")) == set(starter_sets.starter_modules("religious")) - {
        "donations",
        "news",
    }  # Donations and News are Grove (W14-R25, W15-R23)
    assert set(plans.starting_modules("grove", "religious")) == set(starter_sets.starter_modules("religious"))
    assert plans.starting_modules("square") == plans.starting_modules("square", "cultural")  # unchanged default
    assert set(plans.starting_modules("event", "religious")) == set(plans.allowed_modules("event"))  # the Event pass has its own fixed list


def test_the_list_of_starter_sets_is_served(api: Flask) -> None:
    c, h = _login(api, "ss1")
    items = c.get(f"{PREFIX}/starter-sets", headers=h).json["items"]
    assert [i["key"] for i in items] == ["cultural", "religious", "band", "charity"]
    assert items[1]["modules"] == starter_sets.starter_modules("religious") and items[1]["label"] == "Religious community"


def test_a_religious_square_starts_with_its_set_and_a_default_square_is_cultural(api: Flask) -> None:
    c, h = _login(api, "ss2")
    religious = _create(c, h, "faith-club", group_type="religious").json
    assert religious["group_type"] == "religious" and set(religious["modules"]) == set(starter_sets.starter_modules("religious")) - {"donations", "news"}
    default = _create(c, h, "plain-club").json
    assert default["group_type"] == "cultural" and default["modules"] == plans.starting_modules("square", "cultural")


def test_explicit_modules_win_over_the_set_an_unknown_kind_is_refused_and_the_event_pass_has_no_kind(api: Flask) -> None:
    c, h = _login(api, "ss3")
    chosen = _create(c, h, "own-choice", group_type="religious", modules=["events", "payments"]).json
    assert chosen["modules"] == ["events", "payments"] and chosen["group_type"] == "religious"
    assert _create(c, h, "bad-kind", group_type="spaceship").status_code == 422
    event = _create(c, h, "one-event", launch_package="event", group_type="religious").json
    assert event["group_type"] is None and set(event["modules"]) == set(plans.allowed_modules("event"))
