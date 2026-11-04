# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""True sleep (rootsquares W10-R44): Keep copies the public contact details, the square shows as sleeping, the project is paused at the provider only when
PROVIDER_SLEEP is on, wake starts it again. The provider calls are checked against fake HTTP answers, never a real project."""

import json
from unittest.mock import patch

import httpx
from flask import Flask

from app.platform import sleep as sleep_service
from app.platform.models import AuditLog, Square
from tests.conftest import make_settings
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

CONTACT = {"contact_email": "hello@club.example", "contact_phone": "+47 123 45 678", "contact_address": "Torget 1, Oslo"}


def _square(api: Flask, who: str):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    sq = c.post(f"{PREFIX}/squares", json={"name": f"Sq {who}", "slug": f"sq-{who}", "theme_id": "paper-brick"}, headers=h).json
    return c, h, sq


def _row(api: Flask, square_id: str) -> Square:
    with api.extensions["db_factory"]()() as db:
        sq = db.get(Square, __import__("uuid").UUID(square_id))
        assert sq is not None
        db.expunge(sq)
        return sq


def test_going_to_sleep_copies_the_public_contact_and_shows_it_as_sleeping(api: Flask) -> None:
    c, h, sq = _square(api, "sl1")
    base = len(api.extensions["executor"].jobs)  # creating the square queued its provisioning
    with patch("app.platform.routes.sleep_service.fetch_contact", return_value=CONTACT):
        out = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h).json
    assert out["running_plan"] == "keep" and out["sleep_state"] == "sleeping"
    assert sleep_service.contact_of(_row(api, sq["id"])) == CONTACT
    assert len(api.extensions["executor"].jobs) == base + 1  # the pause at the provider runs in the background
    again = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h).json
    assert again["sleep_state"] == "sleeping" and len(api.extensions["executor"].jobs) == base + 1  # already asleep: nothing more


def test_sleep_still_works_when_the_contact_cannot_be_asked(api: Flask) -> None:
    c, h, sq = _square(api, "sl2")
    out = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
    assert out.status_code == 200 and out.json["sleep_state"] == "sleeping" and sleep_service.contact_of(_row(api, sq["id"])) == {k: "" for k in CONTACT}


def test_waking_without_a_provider_pause_is_at_once_and_deletes_the_contact_copy(api: Flask) -> None:
    c, h, sq = _square(api, "sl3")
    with patch("app.platform.routes.sleep_service.fetch_contact", return_value=CONTACT):
        c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
    out = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "live"}, headers=h).json
    assert out["running_plan"] == "live" and out["sleep_state"] == "awake" and _row(api, sq["id"]).sleep_contact is None


def test_waking_a_paused_project_takes_a_background_job(api: Flask) -> None:
    c, h, sq = _square(api, "sl4")
    base = len(api.extensions["executor"].jobs)
    with api.extensions["db_factory"]()() as db:
        row = db.get(Square, __import__("uuid").UUID(sq["id"]))
        assert row is not None
        row.provider_project_ref = "abcdefgh"
        db.commit()
    api.extensions["settings"].__dict__["PROVIDER_SLEEP"] = True
    try:
        c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
        out = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "live"}, headers=h).json
        assert out["sleep_state"] == "waking" and len(api.extensions["executor"].jobs) == base + 2
    finally:
        api.extensions["settings"].__dict__["PROVIDER_SLEEP"] = False


def _client(calls: list[tuple[str, str]], status: str = "ACTIVE_HEALTHY") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/endpoints"):
            return httpx.Response(200, json={"endpoints": [{"id": "ep-1"}, {"id": "ep-2"}]})
        if request.method == "GET" and request.url.path.startswith("/v1/projects/"):
            return httpx.Response(200, json={"status": status})
        return httpx.Response(200, json={})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")


def test_nothing_is_paused_at_a_provider_unless_the_switch_is_on() -> None:
    sq = Square(slug="x", provider_project_ref="abcdefgh")
    calls: list[tuple[str, str]] = []
    assert sleep_service.pause_resources(make_settings(), sq, _client(calls)) is False and calls == []


def test_supabase_is_paused_and_restored_through_the_management_api() -> None:
    s = make_settings(PROVIDER_SLEEP=True)
    sq = Square(slug="x", provider_project_ref="abcdefgh")
    calls: list[tuple[str, str]] = []
    assert sleep_service.pause_resources(s, sq, _client(calls)) is True
    assert sleep_service.resume_resources(s, sq, _client(calls), sleep=lambda _x: None) is True
    assert calls[0] == ("POST", "/v1/projects/abcdefgh/pause")
    assert ("POST", "/v1/projects/abcdefgh/restore") in calls and calls[-1] == ("GET", "/v1/projects/abcdefgh")  # then it waits until healthy


def test_neon_computes_are_suspended_and_started() -> None:
    s = make_settings(PROVIDER_SLEEP=True)
    sq = Square(slug="x", neon_project_id="proj-1")
    calls: list[tuple[str, str]] = []
    sleep_service.pause_resources(s, sq, _client(calls))
    sleep_service.resume_resources(s, sq, _client(calls))
    assert ("POST", "/projects/proj-1/endpoints/ep-1/suspend") in calls and ("POST", "/projects/proj-1/endpoints/ep-2/suspend") in calls
    assert ("POST", "/projects/proj-1/endpoints/ep-1/start") in calls


def test_a_local_square_has_nothing_to_pause() -> None:
    assert sleep_service.pause_resources(make_settings(PROVIDER_SLEEP=True), Square(slug="x"), _client([])) is False


def test_the_wake_job_makes_the_square_awake_or_failed(api: Flask) -> None:
    c, h, sq = _square(api, "sl5")
    import uuid

    factory = api.extensions["db_factory"]()
    with factory() as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None
        row.sleep_state, row.running_plan, row.sleep_contact = "waking", "live", json.dumps(CONTACT)
        db.commit()
    sleep_service.run_wake(factory, make_settings(), uuid.UUID(sq["id"]))
    after = _row(api, sq["id"])
    assert after.sleep_state == "awake" and after.sleep_contact is None
    with factory() as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None
        row.sleep_state, row.provider_project_ref = "waking", "abcdefgh"
        db.commit()
    broken = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"message": "no"})), base_url="https://api.test")
    sleep_service.run_wake(factory, make_settings(PROVIDER_SLEEP=True), uuid.UUID(sq["id"]), client=broken, sleep=lambda _x: None)
    assert _row(api, sq["id"]).sleep_state == "failed"
    with factory() as db:
        actions = [a.action for a in db.query(AuditLog).filter(AuditLog.entity_id == sq["id"]).all()]
    assert "square.woke" in actions and "square.wake_failed" in actions


def _pay(c, h, sq, plan: str, interval: str = "month"):
    body = {"kind": "running", "running_plan": plan, "interval": interval}
    oid = c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json=body, headers=h).json["order_id"]
    return c.post(f"{PREFIX}/billing/orders/{oid}/fake-confirm", json={"outcome": "paid"}, headers=h)


def test_paying_for_keep_puts_the_square_to_sleep_and_paying_for_live_wakes_it(api: Flask) -> None:
    c, h, sq = _square(api, "sl6")
    base = len(api.extensions["executor"].jobs)
    with patch("app.platform.routes.sleep_service.fetch_contact", return_value=CONTACT):
        assert _pay(c, h, sq, "keep").status_code == 200
    asleep = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert asleep["running_plan"] == "keep" and asleep["sleep_state"] == "sleeping" and asleep["paid_until"]
    assert len(api.extensions["executor"].jobs) == base + 1  # the pause at the provider is queued, as with the Put to sleep button
    assert sleep_service.contact_of(_row(api, sq["id"])) == CONTACT
    assert _pay(c, h, sq, "live").status_code == 200
    awake = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert awake["running_plan"] == "live" and awake["sleep_state"] == "awake"
