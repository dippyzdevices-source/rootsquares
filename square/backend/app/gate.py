"""The site gate of the square server (W26-R20, ADR 099): the same gate as the platform's (backend/app/shared/gate.py), written again here because the two servers are separate
codebases. `SITE_GATE_PASSWORD` empty = no gate. Set (16 characters or more) = every `/api/` request is refused with HTTP 401 `gate_required` unless it carries the cookie
`rs_gate`, which only the right passcode earns at `POST /api/gate`. Always open: the CORS preflight, `/api/gate` itself, `/api/health`, the platform's key-protected
`/api/internal/` calls and the providers' signed `/api/webhooks/`. Paths outside `/api/` (the built site, if this server serves it) are not touched: a site's files hold no data.

The gate is handled before the square is looked up from the host, so it answers on every host name, known or not. The cookie holds an expiry and an HMAC of it under a key made
from the passcode (changing the passcode ends every pass; the passcode is never in the cookie); it is HttpOnly, SameSite=Lax, Secure in production. A wrong passcode counts
against the caller's address; behind Render's proxy `PROXY_HOPS` says which entry of `X-Forwarded-For` (counted from the right) is the caller.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from collections import defaultdict, deque

from flask import Flask, Response, current_app, jsonify, request

log = logging.getLogger("app.gate")
COOKIE = "rs_gate"
GATE_PATH = "/api/gate"
OPEN_EXACT = (GATE_PATH, "/api/health")
OPEN_PREFIXES = ("/api/internal/", "/api/webhooks/")
GATE_ATTEMPTS = 8
GATE_WINDOW_SECONDS = 600
MIN_PASSCODE = 16

_tries: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _key(passcode: str) -> bytes:
    return hashlib.sha256(b"rootsquares-site-gate-v1|" + passcode.encode()).digest()


def make_token(passcode: str, hours: int, now: float | None = None) -> str:
    expires = int((now if now is not None else _now()) + hours * 3600)
    return f"{expires}.{hmac.new(_key(passcode), f'gate|{expires}'.encode(), hashlib.sha256).hexdigest()}"


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
    """The caller's address; with a proxy in front, the X-Forwarded-For entry `hops` places from the right (the one the proxy added)."""
    if hops > 0:
        parts = [p.strip() for p in request.headers.get("X-Forwarded-For", "").split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.remote_addr or "unknown"


def _allow_try(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        q = _tries[ip]
        while q and now - q[0] > GATE_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= GATE_ATTEMPTS:
            return False
        q.append(now)
        return True


def _refuse(status: int, code: str, message: str) -> tuple[Response, int]:
    return jsonify({"error": message, "code": code}), status


def validate_gate_config(config) -> None:
    passcode = config.get("SITE_GATE_PASSWORD") or ""
    if passcode and len(passcode) < MIN_PASSCODE:
        raise RuntimeError(f"SITE_GATE_PASSWORD must be at least {MIN_PASSCODE} characters (a gate with a short passcode is no gate)")


def init_gate(app: Flask) -> None:
    """Register the gate. It reads its settings from app.config on every request, so a test (or a restart) can change them."""

    @app.before_request
    def _gate():
        cfg = current_app.config
        passcode = cfg.get("SITE_GATE_PASSWORD") or ""
        path = request.path
        if path == GATE_PATH:
            return _gate_endpoint(passcode, cfg)
        if not passcode or request.method == "OPTIONS" or not path.startswith("/api/") or path in OPEN_EXACT or path.startswith(OPEN_PREFIXES):
            return None
        if token_valid(passcode, request.cookies.get(COOKIE)):
            return None
        return _refuse(401, "gate_required", "This site is private. Enter the passcode first.")


def _gate_endpoint(passcode: str, cfg):
    if request.method == "OPTIONS":
        return None  # the CORS extension answers the preflight
    if request.method == "GET":
        open_now = (not passcode) or token_valid(passcode, request.cookies.get(COOKIE))
        resp = jsonify(required=bool(passcode), open=bool(open_now))
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp
    if request.method != "POST":
        return _refuse(405, "method_not_allowed", "Use GET or POST.")
    if not passcode:
        return jsonify(required=False, open=True)
    ip = client_ip(int(cfg.get("PROXY_HOPS") or 0))
    if not _allow_try(ip):
        return _refuse(429, "gate_rate_limited", "Too many tries. Wait ten minutes and try again.")
    body = request.get_json(silent=True)
    given = str(body.get("passcode") or "") if isinstance(body, dict) else ""
    if not hmac.compare_digest(hashlib.sha256(given.encode()).digest(), hashlib.sha256(passcode.encode()).digest()):
        log.warning("gate_wrong_passcode caller=%s", hashlib.sha256(ip.encode()).hexdigest()[:12])
        return _refuse(401, "gate_wrong", "That is not the passcode.")
    hours = int(cfg.get("SITE_GATE_HOURS") or 168)
    resp = jsonify(required=True, open=True)
    resp.set_cookie(COOKIE, make_token(passcode, hours), max_age=hours * 3600, httponly=True, secure=bool(cfg.get("IS_PRODUCTION")), samesite="Lax", path="/")
    resp.headers["Cache-Control"] = "no-store"
    return resp
