"""The site gate (W26-R20, ADR 099): one shared passcode in front of the whole API, for a staging deploy that must not be seen by anyone who merely finds
the address.

`SITE_GATE_PASSWORD` empty = no gate (development, tests). Set = every request is refused with HTTP 401 `gate_required` unless it carries the cookie
`rs_gate`, which only a correct passcode earns. Always open: the CORS preflight (it cannot carry a cookie), the gate's own address `/gate`, the health
checks, and the payment provider's webhook (which checks its own signature). The gate lives in the server, not in the web pages: the pages are only a
form. A static site cannot be gated, so its files stay downloadable; they hold no data and no secret (guide 42 says so plainly).

The cookie holds an expiry and an HMAC of it under a key made from the passcode, so changing the passcode ends every earlier pass at once and the
passcode is never in the cookie. It is HttpOnly, SameSite=Lax and Secure with `COOKIE_SECURE`. A wrong passcode counts against the caller's address
(`GATE_ATTEMPTS` in `GATE_WINDOW_SECONDS`); behind Render's proxy the address is read from `X-Forwarded-For` as many entries from the right as
`PROXY_HOPS` says (0 = the connection's own address). The passcode must be 16 characters or more.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import structlog
from flask import Flask, Response, current_app, jsonify, request

from app.shared.config import Settings
from app.shared.errors import problem

log = structlog.get_logger("app.gate")
COOKIE = "rs_gate"
GATE_PATH = "/gate"
OPEN_PATHS = (GATE_PATH, "/healthz", "/readyz")
OPEN_ENDPOINT_SUFFIXES = ("billing_webhook",)  # Stripe signs its calls; the handler checks the signature
GATE_ATTEMPTS = 8
GATE_WINDOW_SECONDS = 600
MIN_PASSCODE = 16


def _now() -> float:
    return time.time()


def _key(passcode: str) -> bytes:
    return hashlib.sha256(b"rootsquares-site-gate-v1|" + passcode.encode()).digest()


def make_token(passcode: str, hours: int, now: float | None = None) -> str:
    expires = int((now if now is not None else _now()) + hours * 3600)
    sig = hmac.new(_key(passcode), f"gate|{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def token_valid(passcode: str, token: str | None, now: float | None = None) -> bool:
    if not passcode or not token or "." not in token:
        return False
    expires_text, _, sig = token.partition(".")
    try:
        expires = int(expires_text)
    except ValueError:
        return False
    if expires < (now if now is not None else _now()):
        return False
    good = hmac.new(_key(passcode), f"gate|{expires}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)


def client_ip(hops: int) -> str:
    """The caller's address. With a proxy in front (hops > 0) the entry that many places from the right of X-Forwarded-For (the one the proxy itself added)."""
    if hops > 0:
        parts = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.remote_addr or "unknown"


def _is_open(path: str, endpoint: str | None) -> bool:
    return path in OPEN_PATHS or bool(endpoint and endpoint.endswith(OPEN_ENDPOINT_SUFFIXES))


def register_gate(app: Flask, settings: Settings) -> None:
    passcode = settings.SITE_GATE_PASSWORD
    hours = settings.SITE_GATE_HOURS

    @app.before_request
    def _gate() -> Response | None:
        if not passcode or request.method == "OPTIONS" or _is_open(request.path, request.endpoint):
            return None
        if token_valid(passcode, request.cookies.get(COOKIE)):
            return None
        return problem(401, "gate_required", "This site is private", "Enter the passcode first.")

    @app.get(GATE_PATH)
    def gate_status() -> Response:
        """Is there a gate, and is this browser through it? Always answers (no cookie needed)."""
        open_now = (not passcode) or token_valid(passcode, request.cookies.get(COOKIE))
        resp = jsonify(required=bool(passcode), open=bool(open_now), env=settings.env_label)  # env: the word of the environment strip, display only (W26-R25)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp

    @app.post(GATE_PATH)
    def gate_enter() -> Response:
        if not passcode:
            return jsonify(required=False, open=True, env=settings.env_label)
        ip = client_ip(settings.PROXY_HOPS)
        if not current_app.extensions["providers"].rate_limiter.allow(f"gate:{ip}", GATE_ATTEMPTS, GATE_WINDOW_SECONDS):
            return problem(429, "gate_rate_limited", "Too many tries", "Wait ten minutes and try again.")
        body = request.get_json(silent=True)
        given = str(body.get("passcode") or "") if isinstance(body, dict) else ""
        if not hmac.compare_digest(hashlib.sha256(given.encode()).digest(), hashlib.sha256(passcode.encode()).digest()):
            log.warning("gate_wrong_passcode", caller=hashlib.sha256(ip.encode()).hexdigest()[:12])
            return problem(401, "gate_wrong", "That is not the passcode", "Check it and try again.")
        resp = jsonify(required=True, open=True, env=settings.env_label)
        resp.set_cookie(COOKIE, make_token(passcode, hours), max_age=hours * 3600, httponly=True, secure=settings.COOKIE_SECURE, samesite="Lax", path="/")
        resp.headers["Cache-Control"] = "no-store"
        return resp
