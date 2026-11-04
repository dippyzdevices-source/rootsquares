"""Who is calling the staff API (ADR 083, stage 2). No routes here: the cookie, the session rules and the principal the shared handlers see.

A staff login is the cookie `rs_admin` (HttpOnly, SameSite=Strict, no Domain, so it belongs to the admin host only) holding a signed token with the id
of a `staff_sessions` row. The row counts once its second step is done (TOTP or recovery code), until it is revoked, idle for `STAFF_IDLE_MINUTES` or older
than `STAFF_SESSION_HOURS`. The customer cookies and tokens are never read here, and this cookie is never read by the customer API.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from flask import current_app, g, request

from app.platform.models import StaffSession, StaffUser
from app.shared.config import Settings
from app.shared.crypto import read_token
from app.shared.db import get_session

ADMIN_PREFIX = "/api/admin/v1"
ADMIN_BLUEPRINT = "admin_v1"
STAFF_COOKIE = "rs_admin"
STAFF_CSRF_HEADER, STAFF_CSRF_VALUE = "X-Requested-With", "rootsquares-admin"
TOUCH_EVERY_SECONDS = 60  # last_seen_at is written at most this often


@dataclass(frozen=True)
class StaffPrincipal:
    """What a handler shared with the customer API finds in `g.user` when staff call it: an id, an e-mail and a name (`routes._is_staff()` says it is staff)."""

    id: uuid.UUID
    email: str
    name: str


def settings() -> Settings:
    s: Settings = current_app.extensions["settings"]
    return s


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def on_admin_api() -> bool:
    return request.blueprint == ADMIN_BLUEPRINT


def _aware(d: dt.datetime) -> dt.datetime:
    return d.replace(tzinfo=d.tzinfo or dt.UTC)


def step_of(staff: StaffUser, sess: StaffSession) -> str:
    """'signed_in' once the second step is done; else 'totp' (a second step exists) or 'enrol' (none yet: the person sets it up now)."""
    if sess.second_step_at is not None:
        return "signed_in"
    return "totp" if staff.totp_enabled else "enrol"


def load_session(*, pending_ok: bool) -> tuple[StaffUser, StaffSession] | None:
    """The staff member and session behind the cookie, or None. `pending_ok` also accepts a session whose second step is not done yet."""
    s = settings()
    token = request.cookies.get(STAFF_COOKIE)
    claims = read_token(s.staff_jwt_secret, token, "staff") if token else None
    if not claims:
        return None
    db = get_session()
    try:
        sess = db.get(StaffSession, uuid.UUID(str(claims.get("sid"))))
        staff = db.get(StaffUser, uuid.UUID(claims["sub"]))
    except ValueError:
        return None
    t = now()
    if sess is None or staff is None or sess.staff_id != staff.id or sess.revoked_at is not None or staff.disabled_at is not None:
        return None
    if _aware(sess.expires_at) < t:
        return None
    seen = _aware(sess.last_seen_at or sess.created_at)
    if seen + dt.timedelta(minutes=s.STAFF_IDLE_MINUTES) < t:
        sess.revoked_at = t  # idle too long: the login ends for good
        db.commit()
        return None
    if not pending_ok and sess.second_step_at is None:
        return None
    if (t - seen).total_seconds() >= TOUCH_EVERY_SECONDS:
        sess.last_seen_at = t
        db.commit()
    g.staff, g.staff_session = staff, sess
    return staff, sess


def authenticate() -> StaffPrincipal | None:
    """The shared `login_required` and `admin_required` call this for requests on the staff API; None means not signed in."""
    found = load_session(pending_ok=False)
    if found is None:
        return None
    staff, _ = found
    principal = StaffPrincipal(id=staff.id, email=staff.email, name=staff.name)
    g.user, g.user_id = principal, staff.id
    return principal
