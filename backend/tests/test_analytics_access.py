# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Analytics on the platform (ADR 090, W23-R77): the owner's switch and the owner's numbers, passed on from the square and never stored. SQLite."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from flask import Flask

from app.platform.models import AuditLog
from app.shared.db import Base
from tests.staff_client import ADMIN, STAFF_HEADERS, staff_client
from tests.test_auth_storage import HEADERS, PREFIX, api  # noqa: F401  (api: the app fixture)
from tests.test_square_module_status import _square

ANSWER = {
    "enabled": True,
    "days": 7,
    "from": "2026-10-21",
    "to": "2026-10-27",
    "daily": [{"day": "2026-10-27", "visits": 4, "views": 9, "visitors": 3}],
    "totals": {"visits": 4, "views": 9, "visitors": 3},
    "previous": {"visits": 2, "views": 3, "visitors": 2},
    "pages": [{"path": "/events", "views": 7, "few": False}, {"path": "/rare", "views": None, "few": True}],
    "sources": [{"source": "google.com", "visits": 5, "few": False}],
    "events": [{"slug": "autumn", "title": "Autumn gathering", "views": 12, "views_few": False, "tickets": None, "tickets_few": True}],
}
FETCH = "app.platform.analytics_routes.fetch_square_analytics"


def _url(sq: dict[str, Any]) -> str:
    return f"{PREFIX}/squares/{sq['id']}/analytics"


def test_counting_is_off_until_the_owner_switches_it_on_and_the_square_is_not_asked(api: Flask) -> None:
    c, h, sq = _square(api)
    with patch(FETCH) as ask:
        body = c.get(_url(sq), headers=h).json
    assert body["enabled"] is False and body["totals"] == {"visits": 0, "views": 0, "visitors": 0} and body["daily"] == []
    ask.assert_not_called()


def test_the_owner_switches_counting_on_and_gets_the_squares_numbers(api: Flask) -> None:
    c, h, sq = _square(api)
    assert c.put(_url(sq), json={"enabled": True}, headers=h).json["enabled"] is True
    with patch(FETCH, return_value=ANSWER) as ask:
        body = c.get(_url(sq) + "?days=7", headers=h).json
    assert ask.call_args.args[2] == 7
    assert body["enabled"] is True and body["counting"] is True and body["reachable"] is True and body["days"] == 7
    assert body["start"] == "2026-10-21" and body["end"] == "2026-10-27"
    assert body["totals"] == {"visits": 4, "views": 9, "visitors": 3} and body["previous"]["views"] == 3
    assert body["pages"][1] == {"path": "/rare", "views": None, "few": True}  # a small figure stays hidden
    assert body["events"][0]["tickets"] is None and body["events"][0]["tickets_few"] is True


def test_only_the_known_fields_pass_on_whatever_else_the_square_sends(api: Flask) -> None:
    c, h, sq = _square(api)
    c.put(_url(sq), json={"enabled": True}, headers=h)
    leaky = {
        **ANSWER,
        "visitor_ip": "10.0.0.77",
        "hashes": ["abc"],
        "pages": [{"path": "/x", "views": 9, "few": False, "user_agent": "Firefox"}],
        "totals": {"visits": "many", "views": True, "visitors": 3},
    }
    with patch(FETCH, return_value=leaky):
        text = c.get(_url(sq), headers=h).get_data(as_text=True)
        body = c.get(_url(sq), headers=h).json
    assert "10.0.0.77" not in text and "Firefox" not in text and "hashes" not in text
    assert body["totals"] == {"visits": 0, "views": 0, "visitors": 3}  # a value of the wrong type counts as nothing, never as a number


def test_an_unreachable_or_resting_square_is_said_so(api: Flask) -> None:
    c, h, sq = _square(api)
    c.put(_url(sq), json={"enabled": True}, headers=h)
    with patch(FETCH, return_value=None):
        assert c.get(_url(sq), headers=h).json["reachable"] is False
    with patch(FETCH, return_value={"resting": True}):
        body = c.get(_url(sq), headers=h).json
    assert body["resting"] is True and body["reachable"] is True and body["daily"] == []


def test_only_7_30_and_90_days_are_asked_for(api: Flask) -> None:
    c, h, sq = _square(api)
    c.put(_url(sq), json={"enabled": True}, headers=h)
    asked = []
    with patch(FETCH, side_effect=lambda s, q, d: asked.append(d) or ANSWER):
        for q in ("?days=90", "?days=5", "?days=abc", ""):
            c.get(_url(sq) + q, headers=h)
    assert asked == [90, 30, 30, 30]


def test_switching_is_audited_once_per_change(api: Flask) -> None:
    c, h, sq = _square(api)
    for value in (True, True, False):
        assert c.put(_url(sq), json={"enabled": value}, headers=h).status_code == 200
    with api.extensions["db_factory"]()() as db:
        rows = db.query(AuditLog).filter(AuditLog.action == "analytics.switch").all()
    assert [r.data["enabled"] for r in rows] == [True, False]  # the second True changed nothing


def test_somebody_else_sees_nothing_and_cannot_switch(api: Flask) -> None:
    c, h, sq = _square(api)
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth5:oth5@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.get(_url(sq), headers=other).status_code == 404
    assert c.put(_url(sq), json={"enabled": True}, headers=other).status_code == 404


def test_platform_staff_cannot_see_a_squares_visit_numbers(api: Flask) -> None:
    c, h, sq = _square(api)
    c.put(_url(sq), json={"enabled": True}, headers=h)
    s = staff_client(api)
    assert not [r.rule for r in api.url_map.iter_rules() if r.rule.startswith("/api/admin/v1") and "analytics" in r.rule]
    assert s.get(f"{ADMIN}/squares/{sq['id']}/analytics", headers=STAFF_HEADERS).status_code == 404
    with patch(FETCH, return_value=ANSWER) as ask:
        s.get(f"{ADMIN}/squares/{sq['id']}/analytics", headers=STAFF_HEADERS)
    ask.assert_not_called()


def test_the_platform_stores_the_switch_and_no_number_of_visits(api: Flask) -> None:
    """ADR 090: the one thing the platform keeps about analytics is the owner's switch."""
    names = {f"{t.name}.{c.name}" for t in Base.metadata.tables.values() for c in t.columns}
    named = {n for n in names if any(w in n for w in ("analytics", "visit", "page_view", "pageview", "referrer", "visitor"))}
    assert named == {"squares.analytics_enabled"}, named
    assert not [t for t in Base.metadata.tables if "analytic" in t]
