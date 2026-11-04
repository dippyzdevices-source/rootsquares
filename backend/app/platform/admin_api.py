"""The staff API under /api/admin/v1 (ADR 083, stage 2): sign-in with a password and a second step, and the routes only staff may call.

Two kinds of route live here. The sign-in routes are written below (`/auth/...`). The working routes (the owner console's) are the SAME handlers as in the
customer API, mounted a second time by `mount_shared_routes`: every route behind `admin_required` (an `/owner/...` path loses that prefix) and a short
list of customer routes staff really need (`MIXED`). The handlers find a `StaffPrincipal` in `g.user` there, and the audit log records `actor_staff_id`.
The old `/owner/...` paths of the customer API stay until the admin application (stage 3) has replaced the console, then they go.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any, Literal, cast

from flask import Blueprint, Flask, Response, current_app, request
from pydantic import BaseModel, Field
from spectree import Response as SpecResponse
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult

from app.platform import routes as R
from app.platform import staff as staff_mod
from app.platform.admin_auth import (
    ADMIN_BLUEPRINT,
    ADMIN_PREFIX,
    STAFF_COOKIE,
    STAFF_CSRF_HEADER,
    STAFF_CSRF_VALUE,
    load_session,
    now,
    settings,
    step_of,
)
from app.platform.models import AuditLog, StaffSession, StaffUser
from app.shared.crypto import Encryptor, make_token
from app.shared.db import get_session
from app.shared.errors import ForbiddenError, UnauthorizedError
from app.shared.request_context import get_request_id

# Customer routes (method, path under /api/platform/v1) that staff also use, besides every `admin_required` route. They are mounted unchanged.
MIXED: frozenset[tuple[str, str]] = frozenset(
    {
        ("PUT", "/squares/<uuid:square_id>/custom-package"),
        ("PUT", "/squares/<uuid:square_id>/plan"),
        ("DELETE", "/squares/<uuid:square_id>"),
        ("POST", "/squares/<uuid:square_id>/retry"),
        ("GET", "/billing/orders/<uuid:order_id>/invoice"),
        ("GET", "/prices"),
        ("GET", "/modules"),
    }
)


class StaffLoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class StaffOut(BaseModel):
    id: str
    email: str
    name: str


class StaffSessionOut(BaseModel):
    step: Literal["enrol", "totp", "signed_in"]
    staff: StaffOut


class EnrolStartOut(BaseModel):
    secret: str
    otpauth_uri: str


class RecoveryOut(BaseModel):
    step: Literal["signed_in"]
    recovery_codes: list[str]
    staff: StaffOut


class OkOut(BaseModel):
    ok: bool = True


class SessionRow(BaseModel):
    id: str
    created_at: dt.datetime
    last_seen_at: dt.datetime | None = None
    current: bool
    ip_tag: str | None = None  # a short hash of the address, never the address


class SessionList(BaseModel):
    items: list[SessionRow]


class RevokedOut(BaseModel):
    revoked: int


def _guard() -> None:
    """Two checks before anything else: a browser page from another origin is refused (the customer app is one), and a change needs the staff header."""
    if request.method == "OPTIONS":
        return
    origin = request.headers.get("Origin")
    if origin and origin not in settings().admin_origins:
        raise ForbiddenError("This origin may not use the staff API", code="origin_not_allowed")
    if request.method not in ("GET", "HEAD") and request.headers.get(STAFF_CSRF_HEADER) != STAFF_CSRF_VALUE:
        raise ForbiddenError(f"Send the header {STAFF_CSRF_HEADER}: {STAFF_CSRF_VALUE}", code="csrf_header_required")


def _audit(action: str, staff_id: object = None, **data: object) -> None:
    get_session().add(AuditLog(action=action, entity="staff", entity_id=str(staff_id or ""), actor_staff_id=staff_id, request_id=get_request_id(), data=data))


def _out(staff: StaffUser, sess: StaffSession) -> StaffSessionOut:
    return StaffSessionOut(step=step_of(staff, sess), staff=StaffOut(id=str(staff.id), email=staff.email, name=staff.name))


def _set_cookie(resp: Response, staff: StaffUser, sess: StaffSession) -> None:
    s = settings()
    token = make_token(s.staff_jwt_secret, str(staff.id), "staff", dt.timedelta(hours=s.STAFF_SESSION_HOURS), sid=str(sess.id))
    resp.set_cookie(STAFF_COOKIE, token, max_age=s.STAFF_SESSION_HOURS * 3600, path="/", httponly=True, samesite="Strict", secure=s.COOKIE_SECURE)


def _new_session(staff: StaffUser) -> StaffSession:
    db = get_session()
    t = now()
    db.execute(delete(StaffSession).where(StaffSession.staff_id == staff.id, (StaffSession.expires_at < t) | (StaffSession.revoked_at.is_not(None))))
    sess = StaffSession(
        staff_id=staff.id,
        expires_at=t + dt.timedelta(hours=settings().STAFF_SESSION_HOURS),
        last_seen_at=t,
        ip_tag=hashlib.sha256((request.remote_addr or "").encode()).hexdigest()[:12],
    )
    db.add(sess)
    db.flush()
    return sess


def _full() -> tuple[StaffUser, StaffSession]:
    found = load_session(pending_ok=False)
    if found is None:
        raise UnauthorizedError("Sign in to continue")
    return found


def _pending() -> tuple[StaffUser, StaffSession]:
    found = load_session(pending_ok=True)
    if found is None:
        raise UnauthorizedError("Sign in to continue")
    return found


def _limit(key: str) -> None:
    s = settings()
    if not current_app.extensions["providers"].rate_limiter.allow(key, s.LOGIN_RATE_LIMIT, s.LOGIN_RATE_WINDOW_SECONDS):
        raise R.RateLimitedError("Too many attempts. Wait a minute and try again.", retry_after=s.LOGIN_RATE_WINDOW_SECONDS)


def _second_step_failed(staff: StaffUser, sess: StaffSession) -> None:
    """A wrong code. After MAX_SECOND_STEP_FAILURES of them this login ends (the password is asked again), so a stolen password cannot guess codes for ever."""
    sess.second_step_failures += 1
    _audit("staff.second_step_failed", staff.id)
    if sess.second_step_failures >= staff_mod.MAX_SECOND_STEP_FAILURES:
        sess.revoked_at = now()
        _audit("staff.login_ended_by_codes", staff.id)


def _finish(staff: StaffUser, sess: StaffSession) -> None:
    t = now()
    sess.second_step_at = t
    sess.last_seen_at = t
    staff.last_login_at = t
    _audit("staff.login", staff.id)


@R.api.validate(json=StaffLoginIn, resp=SpecResponse(HTTP_200=StaffSessionOut), tags=["admin"])
def staff_login() -> Response:
    body: StaffLoginIn = request.context.json  # type: ignore[attr-defined]
    email = staff_mod.normalise_email(body.email)
    _limit(f"staff-login:{request.remote_addr}:{email}")
    db = get_session()
    staff = staff_mod.check_password(db, email, body.password, now())
    if staff is None:
        _audit("staff.login_failed", None, email_tag=R._email_tag(email))
        db.commit()
        raise UnauthorizedError("Email or password is wrong", code="invalid_credentials")
    sess = _new_session(staff)
    _audit("staff.password_ok", staff.id)
    if not settings().STAFF_SECOND_STEP_REQUIRED:
        _finish(staff, sess)  # development only (production refuses this setting): the password alone signs in
        _audit("staff.second_step_skipped", staff.id)
    db.commit()
    resp = R._out(_out(staff, sess))
    _set_cookie(resp, staff, sess)
    return resp


@R.api.validate(resp=SpecResponse(HTTP_200=StaffSessionOut), tags=["admin"])
def staff_me() -> Response:
    staff, sess = _pending()
    return R._out(_out(staff, sess))


@R.api.validate(resp=SpecResponse(HTTP_200=EnrolStartOut), tags=["admin"])
def staff_enrol_start() -> Response:
    staff, sess = _pending()
    if step_of(staff, sess) != "enrol":
        raise ForbiddenError("The second step is set up already", code="not_enrolling")
    secret, uri = staff_mod.begin_enrolment(get_session(), Encryptor(settings().staff_fernet_key), staff)
    get_session().commit()
    return R._out(EnrolStartOut(secret=secret, otpauth_uri=uri))


@R.api.validate(json=CodeIn, resp=SpecResponse(HTTP_200=RecoveryOut), tags=["admin"])
def staff_enrol_confirm() -> Response:
    body: CodeIn = request.context.json  # type: ignore[attr-defined]
    staff, sess = _pending()
    if step_of(staff, sess) != "enrol":
        raise ForbiddenError("The second step is set up already", code="not_enrolling")
    _limit(f"staff-2fa:{sess.id}")
    db = get_session()
    try:
        codes = staff_mod.confirm_enrolment(db, Encryptor(settings().staff_fernet_key), staff, body.code)
    except staff_mod.StaffError as e:
        _second_step_failed(staff, sess)
        db.commit()
        raise UnauthorizedError(str(e), code="invalid_code") from e
    _finish(staff, sess)
    db.commit()
    return R._out(RecoveryOut(step="signed_in", recovery_codes=codes, staff=StaffOut(id=str(staff.id), email=staff.email, name=staff.name)))


@R.api.validate(json=CodeIn, resp=SpecResponse(HTTP_200=StaffSessionOut), tags=["admin"])
def staff_totp() -> Response:
    body: CodeIn = request.context.json  # type: ignore[attr-defined]
    staff, sess = _pending()
    if step_of(staff, sess) != "totp":
        raise ForbiddenError("There is no second step to answer", code="not_asked")
    _limit(f"staff-2fa:{sess.id}")
    db = get_session()
    if not staff_mod.verify_second_step(db, Encryptor(settings().staff_fernet_key), staff, body.code):
        _second_step_failed(staff, sess)
        db.commit()
        raise UnauthorizedError("That code is not right", code="invalid_code")
    _finish(staff, sess)
    db.commit()
    return R._out(_out(staff, sess))


@R.api.validate(resp=SpecResponse(HTTP_200=OkOut), tags=["admin"])
def staff_logout() -> Response:
    found = load_session(pending_ok=True)
    if found is not None:
        found[1].revoked_at = now()
        _audit("staff.logout", found[0].id)
        get_session().commit()
    resp = R._out(OkOut())
    resp.delete_cookie(STAFF_COOKIE, path="/")
    return resp


@R.api.validate(resp=SpecResponse(HTTP_200=SessionList), tags=["admin"])
def staff_sessions() -> Response:
    """The signed-in staff member's own logins, newest first (finished sign-ins only)."""
    staff, current = _full()
    rows = (
        get_session()
        .scalars(
            select(StaffSession)
            .where(
                StaffSession.staff_id == staff.id,
                StaffSession.revoked_at.is_(None),
                StaffSession.expires_at > now(),
                StaffSession.second_step_at.is_not(None),
            )
            .order_by(StaffSession.created_at.desc())
        )
        .all()
    )
    items = [SessionRow(id=str(x.id), created_at=x.created_at, last_seen_at=x.last_seen_at, current=x.id == current.id, ip_tag=x.ip_tag) for x in rows]
    return R._out(SessionList(items=items))


@R.api.validate(resp=SpecResponse(HTTP_200=RevokedOut), tags=["admin"])
def staff_revoke_others() -> Response:
    """End every other login of this staff member; this one stays."""
    staff, current = _full()
    db = get_session()
    others = update(StaffSession).where(StaffSession.staff_id == staff.id, StaffSession.id != current.id, StaffSession.revoked_at.is_(None))
    result = db.execute(others.values(revoked_at=now()))
    _audit("staff.logout_others", staff.id)
    db.commit()
    return R._out(RevokedOut(revoked=cast("CursorResult[Any]", result).rowcount))


@R.api.validate(resp=SpecResponse(HTTP_200=RevokedOut), tags=["admin"])
def staff_logout_all() -> Response:
    """Sign out everywhere: every login of this staff member ends, this one too."""
    staff, _ = _full()
    db = get_session()
    result = db.execute(update(StaffSession).where(StaffSession.staff_id == staff.id, StaffSession.revoked_at.is_(None)).values(revoked_at=now()))
    _audit("staff.logout_all", staff.id)
    db.commit()
    resp = R._out(RevokedOut(revoked=cast("CursorResult[Any]", result).rowcount))
    resp.delete_cookie(STAFF_COOKIE, path="/")
    return resp


def _headers(resp: Response) -> Response:
    """What every staff API answer carries: it is never framed, cached, sniffed, indexed or sent on as a referrer."""
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def build_blueprint(app: Flask) -> Blueprint:
    """The staff blueprint of one app: the sign-in routes above, and the handlers staff share with the customer API mounted a second time (see the module
    note). Built per app, after the customer blueprint is registered (its routes are read from the app) and before this one is."""
    admin_bp = Blueprint(ADMIN_BLUEPRINT, __name__, url_prefix=ADMIN_PREFIX)
    admin_bp.before_request(_guard)
    admin_bp.after_request(_headers)
    for path_, endpoint, view, method in (
        ("/auth/login", "staff_login", staff_login, "POST"),
        ("/auth/me", "staff_me", staff_me, "GET"),
        ("/auth/enrol/start", "staff_enrol_start", staff_enrol_start, "POST"),
        ("/auth/enrol/confirm", "staff_enrol_confirm", staff_enrol_confirm, "POST"),
        ("/auth/totp", "staff_totp", staff_totp, "POST"),
        ("/auth/logout", "staff_logout", staff_logout, "POST"),
        ("/auth/sessions", "staff_sessions", staff_sessions, "GET"),
        ("/auth/sessions/revoke-others", "staff_revoke_others", staff_revoke_others, "POST"),
        ("/auth/logout-all", "staff_logout_all", staff_logout_all, "POST"),
    ):
        admin_bp.add_url_rule(path_, endpoint=endpoint, view_func=view, methods=[method])
    seen: dict[tuple[str, str], str] = {}
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if not rule.endpoint.startswith("platform."):
            continue
        view = app.view_functions[rule.endpoint]
        path = rule.rule.removeprefix(R.API_PREFIX)
        take = sorted(m for m in (rule.methods or set()) - {"HEAD", "OPTIONS"} if getattr(view, "admin_only", False) or (m, path) in MIXED)
        if not take:
            continue
        new = path.removeprefix("/owner") if path.startswith("/owner/") else path
        for m in take:
            if (m, new) in seen:
                raise RuntimeError(f"staff API: {m} {new} would be mounted twice ({seen[(m, new)]} and {rule.endpoint})")
            seen[(m, new)] = rule.endpoint
        admin_bp.add_url_rule(new, endpoint=rule.endpoint.split(".", 1)[1], view_func=view, methods=take)
    return admin_bp
