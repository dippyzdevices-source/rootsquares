"""Support access on the square server (rootsquares ADR 089, W23-R65).

A rootsquares staff member can open this square's own admin for a short time when its owner has granted it on the platform. The staff member carries a token
signed by the platform (`SUPPORT_SESSION_KEY`); this module never trusts it alone. On every request carrying such a token it reads the grant and the session
from the platform database (read only) and enforces what the owner agreed: the grant must be active (not revoked, not over), the session must be open, the part
of the admin must be one of the granted scopes, and a change is allowed only when the owner allowed changes and the part can be changed. Anything not named in
SCOPE_OF is refused (default deny), so a new admin part is closed to support until someone decides.

Nothing here is used without PLATFORM_DATABASE_URL (a single-tenant server has no grants) and without SUPPORT_SESSION_KEY (empty = support access off).
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from dataclasses import dataclass

import jwt
import sqlalchemy as sa
from flask import Flask, current_app, g, jsonify, request

ISSUER, AUDIENCE = "rootsquares-admin", "square-support"  # the platform signs with these claims (backend/app/platform/support.py)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CHANGEABLE = frozenset({"content", "settings"})  # health is a log, members are always read only, whatever the owner allowed
SUPPORT_AUTH_ID = "rootsquares-support"  # the one support user of a square (the square's audit log needs a user row to name)
SUPPORT_EMAIL = "support@rootsquares.com"
SESSION_LOG_EVERY = 3600  # seconds: the opening of a session is written to the square's audit log at most this often per process

# The admin part (Flask blueprint name) each scope opens. A blueprint that is not here is refused for a support session: billing, orders, payments, accounting,
# tickets sold, donations, coupons, messages, the newsletter's recipients, imports, users, the door check-in and every webhook are never offered (ADR 089).
SCOPE_OF: dict[str, str] = {
    **{name: "content" for name in (
        "admin_events", "admin_event_pass", "admin_ticket_types", "admin_gallery", "admin_news", "admin_committee", "admin_founders",
        "admin_magazines", "admin_sponsors", "admin_testimonials", "admin_lookups",
    )},
    "admin_settings": "settings",
    "admin_audit": "health",
    **{name: "members" for name in ("admin_members", "admin_memberships", "admin_membership_types", "admin_membership_followup", "membership_drive")},
}

_metadata = sa.MetaData()  # just the columns read here; the platform owns the real tables
_squares = sa.Table("squares", _metadata, sa.Column("id", sa.Uuid, primary_key=True), sa.Column("slug", sa.String))
_grants = sa.Table(
    "support_grants",
    _metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("square_id", sa.Uuid),
    sa.Column("scopes", sa.JSON),
    sa.Column("allow_changes", sa.Boolean),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
    sa.Column("revoked_at", sa.DateTime(timezone=True)),
)
_sessions = sa.Table(
    "support_sessions",
    _metadata,
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("grant_id", sa.Uuid),
    sa.Column("staff_name", sa.String),
    sa.Column("ended_at", sa.DateTime(timezone=True)),
)


@dataclass(frozen=True)
class SupportContext:
    session_id: str
    name: str
    scopes: tuple[str, ...]
    allow_changes: bool
    ends_at: str


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    return t.replace(tzinfo=dt.timezone.utc) if t is not None and t.tzinfo is None else t


def bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    return header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None


def is_support_token(token: str) -> bool:
    """Does this look like a support token (its issuer)? The signature is not read here; `verify` does that."""
    try:
        return jwt.decode(token, options={"verify_signature": False}).get("iss") == ISSUER
    except jwt.PyJWTError:
        return False


def verify(token: str, key: str) -> dict | None:
    if not key:
        return None  # support access is off on this server
    try:
        return jwt.decode(token, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER, leeway=5)
    except jwt.PyJWTError:
        return None


def session_state(directory, session_id: str, slug: str, now: dt.datetime | None = None) -> dict | None:
    """The session, read from the platform database, if it belongs to this square and is still allowed: the open session, an active grant. None otherwise."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        sid = uuid.UUID(session_id)
    except (ValueError, TypeError):
        return None
    query = (
        sa.select(_sessions.c.staff_name, _sessions.c.ended_at, _grants.c.scopes, _grants.c.allow_changes, _grants.c.expires_at, _grants.c.revoked_at, _squares.c.slug)
        .select_from(_sessions.join(_grants, _grants.c.id == _sessions.c.grant_id).join(_squares, _squares.c.id == _grants.c.square_id))
        .where(_sessions.c.id == sid)
    )
    with directory._platform.connect() as conn:
        row = conn.execute(query).mappings().first()
    if row is None or row["slug"] != slug or row["ended_at"] is not None or row["revoked_at"] is not None:
        return None
    expires = _aware(row["expires_at"])
    if expires is None or expires <= now:
        return None
    scopes = row["scopes"] if isinstance(row["scopes"], list) else []
    return {"name": row["staff_name"], "scopes": tuple(scopes), "allow_changes": bool(row["allow_changes"]), "ends_at": expires.isoformat()}


def _refuse(status: int, code: str, message: str):
    return jsonify({"error": message, "code": code}), status


def decide(blueprint: str | None, method: str, path: str, scopes: tuple[str, ...], allow_changes: bool) -> tuple[bool, str, str]:
    """May a support session with these scopes do this? Returns (allowed, code, message). Default deny: an admin part outside SCOPE_OF is refused."""
    scope = SCOPE_OF.get(blueprint or "")
    if scope is None:
        if method in SAFE_METHODS and not (blueprint or "").startswith("admin_") and not path.startswith("/api/admin/"):
            return True, "", ""  # the public pages and their reads: nothing a visitor cannot see
        return False, "support_scope", "Support access does not reach this part of the square."
    if scope not in scopes:
        return False, "support_scope", "The owner has not granted support access to this part."
    if method not in SAFE_METHODS and not (allow_changes and scope in CHANGEABLE):
        return False, "support_read_only", "This support session can look but not change anything."
    return True, "", ""


def support_user():
    """The square's one support user (created on first use): an admin row, so the square's own audit log can name who did a thing. Hidden from the user list."""
    from app.auth.models import User
    from app.extensions import db

    user = User.query.filter_by(auth_user_id=SUPPORT_AUTH_ID).first()
    if user is None:
        user = User(auth_user_id=SUPPORT_AUTH_ID, auth_provider="support", email=SUPPORT_EMAIL, role="admin")
        db.session.add(user)
        db.session.commit()
    return user


_LOGGED: dict[str, float] = {}  # session id: when its opening was last written to the audit log (this process)


def _audit(ctx: SupportContext, text: str) -> None:
    from app.audit.service import log_action

    try:
        log_action(support_user(), "support_access", text[:400])
    except Exception:  # noqa: BLE001 - a log line must never break the request it describes
        current_app.logger.warning("support: could not write the audit row", exc_info=True)


def init_support(app: Flask, directory) -> None:
    """The guard on every request: only a request that carries a support token is touched."""

    @app.before_request
    def _support_guard():
        token = bearer_token()
        if not token or not is_support_token(token):
            return None
        tenant = g.get("tenant")
        claims = verify(token, app.config.get("SUPPORT_SESSION_KEY", ""))
        if tenant is None or claims is None:
            return _refuse(401, "support_invalid", "The support session is not valid.")
        state = session_state(directory, str(claims.get("sid", "")), tenant.slug)
        if state is None:
            return _refuse(403, "support_ended", "The support access has ended.")
        allowed, code, message = decide(request.blueprint, request.method, request.path, state["scopes"], state["allow_changes"])
        ctx = SupportContext(str(claims["sid"]), state["name"], state["scopes"], state["allow_changes"], state["ends_at"])
        if not allowed:
            _audit(ctx, f"Support ({ctx.name}) was refused: {request.method} {request.path} ({code})")
            return _refuse(403, code, message)
        g.support = ctx
        now = time.monotonic()
        if request.method not in SAFE_METHODS:
            _audit(ctx, f"Support ({ctx.name}) changed something: {request.method} {request.path}")
        elif now - _LOGGED.get(ctx.session_id, -SESSION_LOG_EVERY) >= SESSION_LOG_EVERY and request.path.startswith("/api/auth/me"):
            _LOGGED[ctx.session_id] = now
            _audit(ctx, f"Support ({ctx.name}) opened the admin ({', '.join(ctx.scopes)}; {'changes allowed' if ctx.allow_changes else 'read only'})")
        return None
