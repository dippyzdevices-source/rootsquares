"""The site gate of the square server (ADR 099, W26-R20): no passcode, no gate; with one, every /api/ request needs the cookie the passcode earns, on any host name, while the health
check, the platform's key-protected internal calls and the providers' signed webhooks stay open. A wrong passcode is limited per caller; a pass ends with its expiry or a new passcode."""

import pytest
from flask import Flask

from app import create_app
from app import gate

PASSCODE = "correct-horse-battery-staple-42"


@pytest.fixture
def app() -> Flask:
    a = create_app("testing")
    gate._tries.clear()
    return a


def _code(response) -> str:
    """The error code of a JSON answer, or empty when it is not JSON (a 404 page, a file)."""
    return str((response.get_json(silent=True) or {}).get("code", ""))


def _on(app: Flask, **values) -> None:
    app.config.update(SITE_GATE_PASSWORD=PASSCODE, PROXY_HOPS=1, IS_PRODUCTION=True, **values)


def _enter(client, passcode: str = PASSCODE, ip: str = "203.0.113.5"):
    return client.post("/api/gate", json={"passcode": passcode}, headers={"X-Forwarded-For": f"198.51.100.9, {ip}"})


def test_without_a_passcode_there_is_no_gate(app: Flask) -> None:
    c = app.test_client()
    assert c.get("/api/gate").get_json() == {"required": False, "open": True}
    assert c.get("/api/health").status_code == 200
    assert _code(c.get("/api/events")) != "gate_required"


def test_a_short_passcode_is_refused_at_start() -> None:
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        gate.validate_gate_config({"SITE_GATE_PASSWORD": "short"})
    gate.validate_gate_config({"SITE_GATE_PASSWORD": ""})
    gate.validate_gate_config({"SITE_GATE_PASSWORD": PASSCODE})


def test_every_api_request_is_refused_without_the_cookie_except_the_open_ones(app: Flask) -> None:
    _on(app)
    c = app.test_client()
    for path in ("/api/square/config", "/api/events", "/api/settings"):
        r = c.get(path)
        assert r.status_code == 401 and r.get_json()["code"] == "gate_required", path
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/gate").get_json() == {"required": True, "open": False}
    assert c.get("/api/gate").headers["Cache-Control"] == "no-store"
    assert c.options("/api/events", headers={"Origin": "http://localhost:5274", "Access-Control-Request-Method": "GET"}).status_code != 401
    # the platform's internal calls carry their own key and the providers sign their webhooks: the gate does not stand in front of those
    assert _code(c.get("/api/internal/modules/status")) != "gate_required"
    assert _code(c.post("/api/webhooks/stripe", data=b"{}")) != "gate_required"
    # a path outside /api/ (the built site, when served by this server) is not touched
    assert _code(c.get("/some/page")) != "gate_required"


def test_the_right_passcode_earns_a_cookie_that_opens_the_api(app: Flask) -> None:
    _on(app)
    c = app.test_client()
    assert _enter(c, "wrong-passcode-1234567").status_code == 401
    assert c.get("/api/events").status_code == 401
    r = _enter(c)
    assert r.status_code == 200 and r.get_json() == {"required": True, "open": True}
    cookie = r.headers["Set-Cookie"]
    assert cookie.startswith("rs_gate=") and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie and PASSCODE not in cookie
    assert _code(c.get("/api/events")) != "gate_required"
    assert c.get("/api/gate").get_json() == {"required": True, "open": True}


def test_it_answers_on_a_host_name_that_is_no_square(app: Flask) -> None:
    _on(app)
    c = app.test_client()
    assert c.get("/api/gate", base_url="https://nobody.example.org").get_json() == {"required": True, "open": False}
    assert _enter(c).status_code == 200  # the passcode is checked before any square is looked up


def test_wrong_tries_are_limited_per_caller_not_for_everyone(app: Flask) -> None:
    _on(app)
    c = app.test_client()
    codes = [_enter(c, f"wrong-passcode-{i:03d}-xyz", ip="203.0.113.7").status_code for i in range(9)]
    assert codes == [401] * gate.GATE_ATTEMPTS + [429]
    assert _enter(c, ip="203.0.113.7").status_code == 429
    assert _enter(c, ip="203.0.113.8").status_code == 200


def test_a_pass_ends_with_its_expiry_and_with_a_new_passcode() -> None:
    now = 1_000_000.0
    token = gate.make_token(PASSCODE, 24, now)
    assert gate.token_valid(PASSCODE, token, now + 3600)
    assert not gate.token_valid(PASSCODE, token, now + 25 * 3600)
    assert not gate.token_valid("another-passcode-entirely-99", token, now + 3600)
    expires, _, sig = token.partition(".")
    assert not gate.token_valid(PASSCODE, f"{int(expires) + 99999}.{sig}", now + 3600)
    for junk in (None, "", "abc", "12.", ".34", "x.y"):
        assert not gate.token_valid(PASSCODE, junk, now)
