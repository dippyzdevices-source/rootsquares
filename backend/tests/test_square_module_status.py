# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""The owner's Modules screen asks the square server what a module holds and has pending (rootsquares W8-R27)."""

from unittest.mock import patch

import httpx
from flask import Flask

from app.platform.module_status import fetch_module_status
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _square(api: Flask):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-ms:ms@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    sq = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick"}, headers=h).json
    return c, h, sq


def test_without_a_square_server_the_answer_is_empty_not_an_error(api: Flask) -> None:
    c, h, sq = _square(api)
    body = c.get(f"{PREFIX}/squares/{sq['id']}/modules/status", headers=h).json
    assert body == {"available": False, "items": []}


def test_the_answer_of_the_square_server_is_passed_on(api: Flask) -> None:
    c, h, sq = _square(api)
    answer = [{"key": "newsletter", "holds_data": True, "pending": ["A newsletter is scheduled."], "on": True, "secret_extra": "not passed on"}]
    with patch("app.platform.routes.fetch_module_status", return_value=answer):
        body = c.get(f"{PREFIX}/squares/{sq['id']}/modules/status", headers=h).json
    assert body["available"] is True
    assert body["items"] == [{"key": "newsletter", "holds_data": True, "pending": ["A newsletter is scheduled."]}]  # only these three fields pass through


def test_somebody_else_cannot_ask(api: Flask) -> None:
    c, h, sq = _square(api)
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth2:oth2@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.get(f"{PREFIX}/squares/{sq['id']}/modules/status", headers=other).status_code == 404


def test_fetch_sends_the_key_and_the_squares_host_and_survives_failures() -> None:
    from types import SimpleNamespace

    from app.shared.config import Settings

    settings = Settings(_env_file=None, ENV="test", SQUARE_SERVER_URL="http://square.test", SQUARE_INTERNAL_KEY="k")  # type: ignore[call-arg]
    sq = SimpleNamespace(slug="first-one", domain="first-one.rootsquares.com")
    seen = {}

    def ok(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return httpx.Response(200, json={"items": [{"key": "news"}]}, request=httpx.Request("GET", url))

    with patch("app.platform.module_status.httpx.get", side_effect=ok):
        assert fetch_module_status(settings, sq) == [{"key": "news"}]  # type: ignore[arg-type]
    assert seen["url"] == "http://square.test/api/internal/modules/status"
    assert seen["headers"] == {"X-Internal-Key": "k", "Host": "first-one.rootsquares.com"}

    with patch("app.platform.module_status.httpx.get", side_effect=httpx.ConnectError("down")):
        assert fetch_module_status(settings, sq) is None  # type: ignore[arg-type]
    assert fetch_module_status(Settings(_env_file=None, ENV="test"), sq) is None  # type: ignore[call-arg,arg-type]


def test_platform_staff_cannot_read_it_only_the_squares_own_organisation(api: Flask) -> None:
    c, h, sq = _square(api)
    staff = {**HEADERS, "Authorization": "Bearer fake:u-staff:staff@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Staff club"}, headers=staff).status_code == 201
    with patch("app.platform.routes.fetch_module_status", return_value=[]), patch("app.platform.routes._own_square") as own:
        own.return_value = type("S", (), {"org_id": "00000000-0000-0000-0000-000000000000", "domain": "x", "slug": "x"})()
        assert c.get(f"{PREFIX}/squares/{sq['id']}/modules/status", headers=staff).status_code == 404
