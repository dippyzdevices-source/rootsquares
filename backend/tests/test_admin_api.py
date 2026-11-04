"""The staff API (ADR 083, stage 2): sign-in with a password and a second step, sessions, the two worlds apart, mounted routes, audit actor. SQLite."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import select

from app.main import create_app
from app.platform import admin_api, admin_auth, staff
from app.platform.models import AuditLog, StaffUser
from app.providers.auth import FakeAuthProvider
from app.shared.db import Base
from tests.conftest import make_settings

PREFIX = "/api/admin/v1"
ADMIN_ORIGIN = "http://admin.test"
CUSTOMER_ORIGIN = "http://customer.test"
HEADERS = {"X-Requested-With": "rootsquares-admin"}
PASSWORD = "a-long-staff-password"
EMAIL = "ann@example.com"


class Clock:
    """One clock for the session rules and the TOTP codes, moved by the test."""

    def __init__(self) -> None:
        self.t = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.UTC)

    def advance(self, **kw: float) -> None:
        self.t += dt.timedelta(**kw)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(admin_auth, "now", lambda: c.t)
    monkeypatch.setattr(admin_api, "now", lambda: c.t)
    monkeypatch.setattr(staff, "time", SimpleNamespace(time=lambda: c.t.timestamp()))
    return c


@pytest.fixture
def app(tmp_path: Path, clock: Clock) -> Flask:
    a = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'a.db'}", ADMIN_ORIGINS=ADMIN_ORIGIN, CORS_ORIGINS=CUSTOMER_ORIGIN))
    Base.metadata.create_all(a.extensions["db_engine"]())
    a.extensions["providers"].auth = FakeAuthProvider()
    with a.extensions["db_factory"]()() as db:
        staff.create_staff(db, EMAIL, PASSWORD, name="Ann")
        db.commit()
    return a


def login(c: Any, password: str = PASSWORD, email: str = EMAIL) -> Any:
    return c.post(f"{PREFIX}/auth/login", json={"email": email, "password": password}, headers=HEADERS)


def sign_in_with_enrolment(app: Flask, clock: Clock) -> tuple[Any, str, list[str]]:
    """A client that is fully signed in; also returns the TOTP secret and the recovery codes."""
    c = app.test_client()
    assert login(c).status_code == 200
    secret = c.post(f"{PREFIX}/auth/enrol/start", headers=HEADERS).json["secret"]
    r = c.post(f"{PREFIX}/auth/enrol/confirm", json={"code": staff.totp_code(secret, at=clock.t.timestamp())}, headers=HEADERS)
    assert r.status_code == 200, r.json
    return c, secret, r.json["recovery_codes"]


def test_wrong_unknown_and_disabled_logins_are_refused_and_rate_limited(app: Flask) -> None:
    c = app.test_client()
    for pw, email in (("wrong-password-xx", EMAIL), (PASSWORD, "nobody@example.com")):
        r = login(c, pw, email)
        assert r.status_code == 401 and r.json["code"] == "invalid_credentials"
    assert "set-cookie" not in r.headers
    with app.extensions["db_factory"]()() as db:
        staff.set_disabled(db, staff.get_staff(db, EMAIL), True)  # type: ignore[arg-type]
        db.commit()
    assert login(c).status_code == 401
    for _ in range(6):
        last = login(c, "wrong-password-xx")
    assert last.status_code == 429
    with app.extensions["db_factory"]()() as db:
        failed = db.scalars(select(AuditLog).where(AuditLog.action == "staff.login_failed")).all()
        assert failed and all(a.actor_staff_id is None and EMAIL not in str(a.data) for a in failed)  # a tag, never the address


def test_the_first_sign_in_sets_up_the_second_step(app: Flask, clock: Clock) -> None:
    c = app.test_client()
    r = login(c)
    assert r.status_code == 200 and r.json["step"] == "enrol" and r.json["staff"]["email"] == EMAIL
    cookie = r.headers["Set-Cookie"]
    assert "rs_admin=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Domain" not in cookie
    assert c.get(f"{PREFIX}/auth/me").json["step"] == "enrol"
    assert c.get(f"{PREFIX}/custom-guide").status_code == 401  # a password alone opens nothing
    start = c.post(f"{PREFIX}/auth/enrol/start", headers=HEADERS).json
    assert start["otpauth_uri"].startswith("otpauth://totp/") and start["secret"] in start["otpauth_uri"]
    bad = c.post(f"{PREFIX}/auth/enrol/confirm", json={"code": "000000"}, headers=HEADERS)
    assert bad.status_code == 401 and bad.json["code"] == "invalid_code"
    good = c.post(f"{PREFIX}/auth/enrol/confirm", json={"code": staff.totp_code(start["secret"], at=clock.t.timestamp())}, headers=HEADERS)
    assert good.status_code == 200 and good.json["step"] == "signed_in" and len(good.json["recovery_codes"]) == staff.RECOVERY_CODES
    assert c.get(f"{PREFIX}/auth/me").json["step"] == "signed_in"
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200
    assert c.post(f"{PREFIX}/auth/enrol/start", headers=HEADERS).status_code == 403  # already set up


def test_the_next_sign_in_asks_for_a_code_and_never_twice_for_the_same_one(app: Flask, clock: Clock) -> None:
    _, secret, codes = sign_in_with_enrolment(app, clock)
    clock.advance(seconds=90)
    c = app.test_client()
    assert login(c).json["step"] == "totp"
    assert c.get(f"{PREFIX}/custom-guide").status_code == 401
    assert c.post(f"{PREFIX}/auth/totp", json={"code": "000000"}, headers=HEADERS).status_code == 401
    ok = c.post(f"{PREFIX}/auth/totp", json={"code": staff.totp_code(secret, at=clock.t.timestamp())}, headers=HEADERS)
    assert ok.status_code == 200 and ok.json["step"] == "signed_in"
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200
    again = app.test_client()
    login(again)
    replay = again.post(f"{PREFIX}/auth/totp", json={"code": staff.totp_code(secret, at=clock.t.timestamp())}, headers=HEADERS)
    assert replay.status_code == 401  # the same time step
    third = app.test_client()
    login(third)
    assert third.post(f"{PREFIX}/auth/totp", json={"code": codes[0]}, headers=HEADERS).status_code == 200  # a recovery code, once
    fourth = app.test_client()
    login(fourth)
    assert fourth.post(f"{PREFIX}/auth/totp", json={"code": codes[0]}, headers=HEADERS).status_code == 401


def test_logout_ends_the_login(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200
    assert c.post(f"{PREFIX}/auth/logout", headers=HEADERS).status_code == 200
    assert c.get(f"{PREFIX}/custom-guide").status_code == 401


def test_an_idle_login_ends(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    clock.advance(minutes=20)
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200  # a request keeps it alive
    clock.advance(minutes=20)
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200
    clock.advance(minutes=31)
    assert c.get(f"{PREFIX}/custom-guide").status_code == 401


def test_a_login_ends_after_its_absolute_time(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    for _ in range(17):  # active every 29 minutes: idle never triggers, the 8 hours do
        clock.advance(minutes=29)
        status = c.get(f"{PREFIX}/custom-guide").status_code
        if clock.t >= dt.datetime(2026, 10, 23, 20, 0, tzinfo=dt.UTC):
            break
    assert status == 401


def test_disabling_a_staff_member_ends_a_login_in_progress(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    assert c.get(f"{PREFIX}/custom-guide").status_code == 200
    with app.extensions["db_factory"]()() as db:
        m = staff.get_staff(db, EMAIL)
        assert m is not None
        staff.set_disabled(db, m, True)
        db.commit()
    assert c.get(f"{PREFIX}/custom-guide").status_code == 401


def test_a_change_needs_the_header_and_the_origin_must_be_the_admin_application(app: Flask) -> None:
    c = app.test_client()
    r = c.post(f"{PREFIX}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 403 and r.json["code"] == "csrf_header_required"
    r = c.post(f"{PREFIX}/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers={**HEADERS, "Origin": CUSTOMER_ORIGIN})
    assert r.status_code == 403 and r.json["code"] == "origin_not_allowed"
    r = c.post(f"{PREFIX}/auth/login", json={"email": EMAIL, "password": PASSWORD}, headers={**HEADERS, "Origin": ADMIN_ORIGIN})
    assert r.status_code == 200
    pre = c.options(f"{PREFIX}/auth/login", headers={"Origin": ADMIN_ORIGIN, "Access-Control-Request-Method": "POST"})
    assert pre.headers.get("Access-Control-Allow-Origin") == ADMIN_ORIGIN and pre.headers.get("Access-Control-Allow-Credentials") == "true"
    pre = c.options(f"{PREFIX}/auth/login", headers={"Origin": CUSTOMER_ORIGIN, "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in pre.headers  # the customer application may not even ask


def test_staff_and_customers_never_stand_in_for_each_other(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    assert c.get("/api/platform/v1/auth/me").status_code == 401  # the staff cookie means nothing to the customer API
    assert c.get("/api/platform/v1/custom-guide").status_code == 404  # and the customer API does not even serve a staff route
    customer = app.test_client()
    bearer = {"Authorization": "Bearer fake:u1:cust@example.com", "X-Requested-With": "rootsquares"}
    assert customer.get("/api/platform/v1/auth/me", headers=bearer).status_code == 200
    assert customer.get(f"{PREFIX}/custom-guide", headers=bearer).status_code == 401  # and a customer is nobody on the staff API


def test_staff_actions_are_audited_with_the_staff_id_only(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    r = c.put(f"{PREFIX}/custom-guide", json={"steps": [0, 5000, 10000, 20000, 40000]}, headers=HEADERS)
    assert r.status_code == 200, r.json
    with app.extensions["db_factory"]()() as db:
        m = staff.get_staff(db, EMAIL)
        assert m is not None
        row = db.scalar(select(AuditLog).where(AuditLog.action == "custom.guide"))
        assert row is not None and row.actor_staff_id == m.id and row.actor_user_id is None
        assert db.scalar(select(AuditLog).where(AuditLog.action == "staff.login")) is not None
        assert db.get(StaffUser, m.id) is not None


def test_every_admin_only_route_is_mounted_on_the_staff_api(app: Flask) -> None:
    views = app.view_functions
    rules = list(app.url_map.iter_rules())
    customer = {r.endpoint.split(".", 1)[1] for r in rules if r.endpoint.startswith("platform.") and getattr(views[r.endpoint], "admin_only", False)}
    mounted = {r.endpoint.split(".", 1)[1] for r in app.url_map.iter_rules() if r.endpoint.startswith("admin_v1.")}
    assert len(customer) > 40
    assert customer <= mounted
    assert all(r.rule.startswith(PREFIX) for r in app.url_map.iter_rules() if r.endpoint.startswith("admin_v1."))
    assert not any("/owner" in r.rule for r in app.url_map.iter_rules() if r.endpoint.startswith("admin_v1."))


def test_the_audit_log_shows_staff_as_staff(app: Flask, clock: Clock) -> None:
    c, _, _ = sign_in_with_enrolment(app, clock)
    assert c.put(f"{PREFIX}/custom-guide", json={"steps": [0, 5000, 10000, 20000, 40000]}, headers=HEADERS).status_code == 200
    items = c.get(f"{PREFIX}/audit?action_prefix=custom.").json["items"]
    assert len(items) == 1 and items[0]["actor_kind"] == "staff" and items[0]["actor_email"] == EMAIL
    actor = items[0]["actor_id"]
    assert [i["action"] for i in c.get(f"{PREFIX}/audit?actor_id={actor}").json["items"]].count("custom.guide") == 1  # the filter finds a staff actor too


def test_eight_wrong_passwords_lock_the_account_for_a_while(app: Flask, clock: Clock) -> None:
    app.extensions["providers"].rate_limiter = SimpleNamespace(allow=lambda *a, **k: True)  # the rate limit uses real time; the lock is under test here
    c = app.test_client()
    for i in range(staff.LOCK_AFTER):
        clock.advance(seconds=30)
        assert login(c, f"wrong-password-{i:02d}").status_code == 401
    clock.advance(seconds=30)
    assert login(c).status_code == 401  # the right password is refused while the account is locked, with the same answer
    with app.extensions["db_factory"]()() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "staff.locked")) is not None
    clock.advance(minutes=staff.LOCK_MINUTES + 1)
    assert login(c).status_code == 200  # the lock ends, and a right password clears the count
    with app.extensions["db_factory"]()() as db:
        m = staff.get_staff(db, EMAIL)
        assert m is not None and m.failed_attempts == 0 and m.locked_until is None


def test_wrong_codes_end_the_login(app: Flask, clock: Clock) -> None:
    _, secret, _ = sign_in_with_enrolment(app, clock)
    clock.advance(seconds=90)
    c = app.test_client()
    assert login(c).json["step"] == "totp"
    for i in range(staff.MAX_SECOND_STEP_FAILURES):
        clock.advance(seconds=15)
        assert c.post(f"{PREFIX}/auth/totp", json={"code": f"00000{i}"}, headers=HEADERS).status_code == 401
    clock.advance(seconds=40)
    good = staff.totp_code(secret, at=clock.t.timestamp())
    assert c.post(f"{PREFIX}/auth/totp", json={"code": good}, headers=HEADERS).status_code == 401  # this login is over; even a right code is too late
    assert c.get(f"{PREFIX}/auth/me").status_code == 401


def test_a_staff_member_sees_and_ends_their_own_logins(app: Flask, clock: Clock) -> None:
    first, secret, _ = sign_in_with_enrolment(app, clock)
    clock.advance(seconds=90)
    second = app.test_client()
    login(second)
    second.post(f"{PREFIX}/auth/totp", json={"code": staff.totp_code(secret, at=clock.t.timestamp())}, headers=HEADERS)
    rows = first.get(f"{PREFIX}/auth/sessions").json["items"]
    assert len(rows) == 2 and sum(1 for r in rows if r["current"]) == 1 and all(len(r["ip_tag"]) == 12 for r in rows)
    assert first.post(f"{PREFIX}/auth/sessions/revoke-others", headers=HEADERS).json["revoked"] == 1
    assert second.get(f"{PREFIX}/custom-guide").status_code == 401 and first.get(f"{PREFIX}/custom-guide").status_code == 200
    assert first.post(f"{PREFIX}/auth/logout-all", headers=HEADERS).json["revoked"] == 1
    assert first.get(f"{PREFIX}/custom-guide").status_code == 401


def test_every_staff_answer_carries_the_security_headers(app: Flask) -> None:
    r = app.test_client().get(f"{PREFIX}/auth/me")
    assert r.status_code == 401
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["Cache-Control"] == "no-store" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer" and "noindex" in r.headers["X-Robots-Tag"]
    assert "X-Frame-Options" not in app.test_client().get("/api/platform/v1/auth/me").headers  # the customer API is not touched


def test_with_the_second_step_off_for_development_the_password_alone_signs_in(tmp_path: Path, clock: Clock) -> None:
    """STAFF_SECOND_STEP_REQUIRED=false (W26-R11, development only): no code is asked, the session counts at once, the audit log says so."""
    a = create_app(
        make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'b.db'}", ADMIN_ORIGINS=ADMIN_ORIGIN, CORS_ORIGINS=CUSTOMER_ORIGIN, STAFF_SECOND_STEP_REQUIRED=False)
    )
    Base.metadata.create_all(a.extensions["db_engine"]())
    a.extensions["providers"].auth = FakeAuthProvider()
    with a.extensions["db_factory"]()() as db:
        staff.create_staff(db, EMAIL, PASSWORD, name="Ann")
        db.commit()
    c = a.test_client()
    r = login(c)
    assert r.status_code == 200 and r.json["step"] == "signed_in"
    assert c.get(f"{PREFIX}/auth/me", headers=HEADERS).json["step"] == "signed_in"
    assert login(c, password="wrong-password-here").status_code == 401  # the password is still checked
    with a.extensions["db_factory"]()() as db:
        actions = [row.action for row in db.scalars(select(AuditLog))]
    assert "staff.second_step_skipped" in actions
