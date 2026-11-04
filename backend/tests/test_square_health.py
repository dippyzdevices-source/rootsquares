# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""The owner's Health tab (rootsquares W10-R19, ADR 038): states and sentences only; the owner's own organisation only."""

from unittest.mock import patch

from flask import Flask

from tests.test_auth_storage import HEADERS, PREFIX, api  # noqa: F401  (api: the app fixture)
from tests.test_square_module_status import _square


def test_unreachable_server_is_reported_not_raised(api: Flask) -> None:
    c, h, sq = _square(api)
    body = c.get(f"{PREFIX}/squares/{sq['id']}/health", headers=h).json
    assert body["reachable"] is False
    assert {x["key"] for x in body["checks"]} == {"reachable", "site_logo"}


def test_only_known_fields_of_the_square_report_pass_on(api: Flask) -> None:
    c, h, sq = _square(api)
    report = {"version": "1.2", "checks": [{"key": "database", "group": "system", "state": "ok", "text": "The database answers.", "rows": 99}]}
    with patch("app.platform.routes.fetch_square_health", return_value=report):
        body = c.get(f"{PREFIX}/squares/{sq['id']}/health", headers=h).json
    assert body["reachable"] is True and body["version"] == "1.2"
    assert body["checks"][1] == {"key": "database", "group": "system", "state": "ok", "text": "The database answers."}


def test_somebody_else_cannot_see_the_health(api: Flask) -> None:
    c, h, sq = _square(api)
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth3:oth3@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.get(f"{PREFIX}/squares/{sq['id']}/health", headers=other).status_code == 404
