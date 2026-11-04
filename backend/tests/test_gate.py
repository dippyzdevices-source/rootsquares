"""The site gate (ADR 099, W26-R20): off when no passcode is set; with one, the whole API refuses a caller without the cookie, the cookie is
earned by the passcode only, a wrong passcode is limited per caller, a pass ends with its expiry or when the passcode changes, health checks
and the payment webhook stay open. No network."""

from __future__ import annotations

import pytest
from flask import Flask
from pydantic import ValidationError

from app.main import create_app
from app.shared import gate
from tests.conftest import make_settings

PASSCODE = "correct-horse-battery-staple-42"
API = "/api/platform/v1"


def _app(**changes: object) -> Flask:
    return create_app(make_settings(SITE_GATE_PASSWORD=PASSCODE, COOKIE_SECURE=True, PROXY_HOPS=1, CORS_ORIGINS="https://site.test", **changes))


def _enter(client, passcode: str = PASSCODE, ip: str = "203.0.113.5"):
    return client.post("/gate", json={"passcode": passcode}, headers={"X-Forwarded-For": f"198.51.100.9, {ip}"})


def test_no_passcode_means_no_gate() -> None:
    c = create_app(make_settings()).test_client()
    assert c.get("/gate").get_json() == {"required": False, "open": True, "env": ""}
    assert c.get(f"{API}/me").get_json().get("code") != "gate_required"


def test_the_status_carries_the_word_of_the_environment_strip() -> None:
    """W26-R25, display only: ENV_LABEL, else Local on a development machine, else nothing; it is in every answer of /gate and changes nothing else."""
    assert create_app(make_settings(ENV="local")).test_client().get("/gate").get_json() == {"env": "Local", "open": True, "required": False}
    assert create_app(make_settings(ENV="local", ENV_LABEL="Staging")).test_client().get("/gate").get_json()["env"] == "Staging"
    assert create_app(make_settings(ENV="test")).test_client().get("/gate").get_json()["env"] == ""
    closed = _app(ENV_LABEL=" Staging ").test_client()
    assert closed.get("/gate").get_json() == {"env": "Staging", "open": False, "required": True}  # the gate stays shut; the word is still told
    assert _enter(closed).get_json()["env"] == "Staging"


def test_the_gate_answers_the_customer_app_and_the_admin_application_with_the_cookie_allowed() -> None:
    """W26-R25: both sites ask /gate at start-up (the passcode, the word of the strip); one process serving both surfaces must allow each origin."""
    app = create_app(make_settings(CORS_ORIGINS="https://site.test", ADMIN_ORIGINS="https://admin.test"))
    c = app.test_client()
    for origin in ("https://site.test", "https://admin.test"):
        r = c.get("/gate", headers={"Origin": origin})
        assert r.headers["Access-Control-Allow-Origin"] == origin and r.headers["Access-Control-Allow-Credentials"] == "true", origin
    assert "Access-Control-Allow-Origin" not in c.get("/gate", headers={"Origin": "https://stranger.test"}).headers
    admin_only = create_app(make_settings(API_SURFACE="admin", ADMIN_ORIGINS="https://admin.test")).test_client()
    assert admin_only.get("/gate", headers={"Origin": "https://admin.test"}).headers["Access-Control-Allow-Origin"] == "https://admin.test"


def test_a_short_passcode_is_refused_when_the_server_starts() -> None:
    with pytest.raises(ValidationError, match="at least 16 characters"):
        make_settings(SITE_GATE_PASSWORD="short-one")


def test_everything_is_refused_without_the_cookie_except_the_open_paths() -> None:
    c = _app().test_client()
    r = c.get(f"{API}/me")
    assert r.status_code == 401 and r.get_json()["code"] == "gate_required"
    assert c.get(f"{API}/public/hosts/anything.test").status_code == 401  # the public square data is behind the gate too
    assert c.get("/healthz").status_code == 200
    assert c.get("/gate").get_json() == {"required": True, "open": False, "env": ""}
    assert c.get("/gate").headers["Cache-Control"] == "no-store"
    # a CORS preflight cannot carry a cookie and must not be refused
    pre = c.options(f"{API}/me", headers={"Origin": "https://site.test", "Access-Control-Request-Method": "GET"})
    assert pre.status_code != 401
    # the payment webhook is signed by the provider, so the gate lets it through to its own check (which refuses an unsigned call in its own words)
    hook = c.post(f"{API}/billing/webhook", data=b"{}")
    assert hook.get_json().get("code") != "gate_required"


def test_the_right_passcode_earns_a_cookie_that_opens_the_api() -> None:
    c = _app().test_client()
    assert _enter(c, "wrong-passcode-1234567").status_code == 401
    assert c.get(f"{API}/me").get_json()["code"] == "gate_required"
    r = _enter(c)
    assert r.status_code == 200 and r.get_json() == {"required": True, "open": True, "env": ""}
    cookie = r.headers["Set-Cookie"]
    assert cookie.startswith("rs_gate=") and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    assert PASSCODE not in cookie  # the passcode is never in the cookie
    after = c.get(f"{API}/me")
    assert after.get_json().get("code") != "gate_required"  # through the gate; the person is simply not signed in
    assert c.get("/gate").get_json() == {"required": True, "open": True, "env": ""}


def test_wrong_tries_are_limited_per_caller_not_for_everyone() -> None:
    c = _app().test_client()
    codes = [_enter(c, f"wrong-passcode-{i:03d}-xyz", ip="203.0.113.7").status_code for i in range(9)]
    assert codes == [401] * gate.GATE_ATTEMPTS + [429]
    assert _enter(c, ip="203.0.113.7").status_code == 429  # even the right passcode waits for the window
    assert _enter(c, ip="203.0.113.8").status_code == 200  # another caller is not affected


def test_a_pass_ends_with_its_expiry_and_with_a_new_passcode() -> None:
    now = 1_000_000.0
    token = gate.make_token(PASSCODE, 24, now)
    assert gate.token_valid(PASSCODE, token, now + 3600)
    assert not gate.token_valid(PASSCODE, token, now + 25 * 3600)  # expired
    assert not gate.token_valid("another-passcode-entirely-99", token, now + 3600)  # the passcode changed: every old pass is void
    expires, _, sig = token.partition(".")
    assert not gate.token_valid(PASSCODE, f"{int(expires) + 99999}.{sig}", now + 3600)  # the expiry cannot be stretched
    assert not gate.token_valid(PASSCODE, f"{expires}.{'0' * 64}", now + 3600)
    for junk in (None, "", "abc", "12.", ".34", "x.y"):
        assert not gate.token_valid(PASSCODE, junk, now)


def test_the_caller_is_read_from_the_right_of_the_forwarded_header() -> None:
    app = Flask(__name__)
    with app.test_request_context("/", headers={"X-Forwarded-For": "6.6.6.6, 198.51.100.9, 203.0.113.5"}, environ_base={"REMOTE_ADDR": "10.0.0.1"}):
        assert gate.client_ip(1) == "203.0.113.5"  # the entry the one proxy added: a caller cannot choose it
        assert gate.client_ip(2) == "198.51.100.9"
        assert gate.client_ip(0) == "10.0.0.1"
        assert gate.client_ip(9) == "10.0.0.1"
