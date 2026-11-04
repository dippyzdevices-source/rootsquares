"""Support access on the square server (rootsquares ADR 089, W23-R65): a platform-signed token is only the start; the grant is read from the platform database on every
request, the scope and read only are enforced, anything not named is refused, and the square's own audit log names who did what. Fake platform database (sqlite)."""

import base64
import datetime as dt
import hashlib
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.settings.models import SiteSettings
from app import support
from tests.auth_helpers import FakeJWKClient, auth_header, make_token

KEY = "k" * 40
FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()))
HOST = "http://square-a.localhost"
NOW = dt.datetime.now(dt.timezone.utc)


def _enc(value: str) -> str:
    return FERNET.encrypt(value.encode()).decode()


@pytest.fixture
def server(tmp_path: Path):
    """One square (its own database) and a platform database with the `squares`, `support_grants` and `support_sessions` tables."""
    square_url = f"sqlite:///{tmp_path / 'a.db'}"
    engine = create_engine(square_url)
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    with app.app_context():
        db.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(SiteSettings(id=1, contact_email="a@example.org", contact_phone="", contact_address=""))
        s.commit()
    engine.dispose()
    platform_url = f"sqlite:///{tmp_path / 'platform.db'}"
    platform = create_engine(platform_url)
    square_id = uuid.uuid4()
    other_id = uuid.uuid4()
    with platform.begin() as conn:
        conn.execute(
            text(
                "create table squares (id char(32), slug text, name text, theme_id text, domain text, status text, suspended_at text, "
                "db_connection text, provider_secrets text)"
            )
        )
        for sid, slug, domain in ((square_id, "square-a", "square-a.rootsquares.com"), (other_id, "square-b", "square-b.rootsquares.com")):
            conn.execute(
                text("insert into squares values (:id, :slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec)"),
                {"id": sid.hex, "slug": slug, "name": slug, "domain": domain, "url": _enc(square_url), "sec": _enc(json.dumps({"project_url": "https://a.supabase.co", "publishable": "pk"}))},
            )
    support._grants.create(platform)
    support._sessions.create(platform)
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url), patch.object(TestingConfig, "SUPPORT_SESSION_KEY", KEY):
        app = create_app("testing")
    yield app, platform, square_id, other_id
    platform.dispose()


def _open(platform, square_id, scopes, allow_changes=False, *, minutes=60, revoked=False, ended=False, name="Anna") -> str:
    """A grant and one open session on it, written like the platform writes them. Returns the session id."""
    gid, sid = uuid.uuid4(), uuid.uuid4()
    with platform.begin() as conn:
        conn.execute(
            support._grants.insert().values(
                id=gid, square_id=square_id, scopes=scopes, allow_changes=allow_changes, expires_at=NOW + dt.timedelta(minutes=minutes), revoked_at=NOW if revoked else None
            )
        )
        conn.execute(support._sessions.insert().values(id=sid, grant_id=gid, staff_name=name, ended_at=NOW if ended else None))
    return str(sid)


def _token(sid: str, key: str = KEY, **over) -> str:
    claims = {"iss": support.ISSUER, "aud": support.AUDIENCE, "iat": int(NOW.timestamp()), "exp": int((NOW + dt.timedelta(minutes=15)).timestamp()), "sid": sid, **over}
    return jwt.encode(claims, key, algorithm="HS256")


def _square_sql(platform, sql: str) -> list[tuple]:
    """Read the square's own database (the file next to the platform one) outside any request."""
    engine = create_engine(f"sqlite:///{Path(platform.url.database).with_name('a.db')}")
    try:
        with engine.connect() as conn:
            return [tuple(r) for r in conn.execute(text(sql))]
    finally:
        engine.dispose()


def _call(app, method: str, path: str, token: str | None, host: str = HOST, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return getattr(app.test_client(), method)(path, base_url=host, headers=headers, **kw)


# ---- the grant decides ---------------------------------------------------------------------------------------------------------------
def test_an_active_grant_opens_only_its_scope_and_only_to_look(server) -> None:
    app, platform, sq, _ = server
    token = _token(_open(platform, sq, ["content"]))
    assert _call(app, "get", "/api/admin/news", token).status_code == 200  # a granted part, read
    refused = _call(app, "post", "/api/admin/news", token, json={})
    assert refused.status_code == 403 and refused.get_json()["code"] == "support_read_only"
    for path in ("/api/admin/members", "/api/admin/payments", "/api/admin/orders", "/api/admin/users", "/api/admin/donations", "/api/admin/settings"):
        r = _call(app, "get", path, token)
        assert r.status_code == 403 and r.get_json()["code"] == "support_scope", path  # not granted, or never offered


def test_changes_are_allowed_only_for_a_changeable_scope_when_the_owner_allowed_them(server) -> None:
    app, platform, sq, _ = server
    token = _token(_open(platform, sq, ["content", "members"], allow_changes=True))
    assert _call(app, "post", "/api/admin/news", token, json={}).status_code != 403  # allowed: the bad body is the handler's answer, not the guard's
    members = _call(app, "post", "/api/admin/members", token, json={})
    assert members.status_code == 403 and members.get_json()["code"] == "support_read_only"  # members are always read only
    assert _call(app, "get", "/api/admin/members", token).status_code == 200


def test_a_revoked_expired_or_ended_grant_stops_the_next_request(server) -> None:
    app, platform, sq, _ = server
    for kind in ({"revoked": True}, {"minutes": -1}, {"ended": True}):
        token = _token(_open(platform, sq, ["content"], **kind))
        r = _call(app, "get", "/api/admin/news", token)
        assert r.status_code == 403 and r.get_json()["code"] == "support_ended", kind


def test_a_session_of_another_square_does_not_open_this_one(server) -> None:
    app, platform, _, other = server
    token = _token(_open(platform, other, ["content"]))
    assert _call(app, "get", "/api/admin/news", token).get_json()["code"] == "support_ended"


def test_a_token_with_the_wrong_key_or_no_key_is_refused(server, tmp_path) -> None:
    app, platform, sq, _ = server
    sid = _open(platform, sq, ["content"])
    assert _call(app, "get", "/api/admin/news", _token(sid, key="x" * 40)).get_json()["code"] == "support_invalid"
    expired = _token(sid, exp=int((NOW - dt.timedelta(minutes=5)).timestamp()))
    assert _call(app, "get", "/api/admin/news", expired).get_json()["code"] == "support_invalid"
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform.url.render_as_string(hide_password=False)), patch.object(TestingConfig, "SUPPORT_SESSION_KEY", ""):
        off = create_app("testing")
    assert _call(off, "get", "/api/admin/news", _token(sid)).get_json()["code"] == "support_invalid"  # no key on this server: support access is off


def test_who_am_i_says_it_is_a_support_session_and_the_support_user_is_hidden(server) -> None:
    app, platform, sq, _ = server
    token = _token(_open(platform, sq, ["content", "members"], name="Anna"))
    me = _call(app, "get", "/api/auth/me", token).get_json()
    assert me["role"] == "admin" and me["support"]["name"] == "Anna" and me["support"]["scopes"] == ["content", "members"] and me["support"]["allow_changes"] is False
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        owner = _call(app, "get", "/api/admin/users", auth_header(make_token(sub=str(uuid.uuid4()), email="o@example.org", iss="https://a.supabase.co/auth/v1")).get("Authorization", "").removeprefix("Bearer "))
    assert owner.status_code in (401, 403)  # an ordinary member is not an admin
    rows = _square_sql(platform, "select email, role from users where auth_provider = 'support'")
    assert rows == [(support.SUPPORT_EMAIL, "admin")]


def test_public_pages_can_be_read_but_nothing_public_can_be_changed(server) -> None:
    app, platform, sq, _ = server
    token = _token(_open(platform, sq, ["health"], allow_changes=False))
    assert _call(app, "get", "/api/settings", token).status_code == 200
    r = _call(app, "post", "/api/contact", token, json={"name": "x", "email": "x@example.org", "message": "hi"})
    assert r.status_code == 403 and r.get_json()["code"] == "support_scope"


def test_a_support_token_is_not_an_admin_on_a_route_that_no_scope_names(server) -> None:
    app, platform, sq, _ = server
    token = _token(_open(platform, sq, ["content"]))
    assert _call(app, "get", "/api/memberships/me/children-awaiting", token).status_code == 401  # a member route: the support user is nobody here


# ---- the square's own audit log ------------------------------------------------------------------------------------------------------
def test_the_squares_audit_log_names_support_for_a_refusal_a_change_and_the_opening(server) -> None:
    app, platform, sq, _ = server
    sid = _open(platform, sq, ["content"], allow_changes=True, name="Anna")
    token = _token(sid)
    support._LOGGED.clear()
    _call(app, "get", "/api/auth/me", token)  # the page's first call: the opening is logged once
    _call(app, "get", "/api/auth/me", token)
    _call(app, "get", "/api/admin/payments", token)  # refused
    _call(app, "post", "/api/admin/news", token, json={})  # a change
    rows = [r[0] for r in _square_sql(platform, "select description from audit_logs where action = 'support_access' order by id")]
    assert sum("opened the admin" in r for r in rows) == 1
    assert any("was refused: GET /api/admin/payments (support_scope)" in r for r in rows)
    assert any("changed something: POST /api/admin/news" in r for r in rows)
    assert all("Anna" in r for r in rows)


# ---- the scope map -------------------------------------------------------------------------------------------------------------------
NEVER = {  # admin parts support can never reach (ADR 089): decided on purpose, not forgotten
    "admin_accounting", "admin_contributions", "admin_coupons", "admin_donations", "admin_imports", "admin_messages", "admin_newsletter", "admin_orders",
    "admin_payment_providers", "admin_payments", "admin_reports", "admin_tickets", "admin_users", "checkin",
}


def test_every_admin_part_is_either_given_a_scope_or_decided_never(server) -> None:
    """A new admin blueprint fails this test until someone decides: default deny is not enough, the decision must be written down."""
    app, *_ = server
    admin_parts = {r.endpoint.split(".")[0] for r in app.url_map.iter_rules() if "." in r.endpoint and (r.rule.startswith("/api/admin") or r.endpoint.startswith("admin_"))}
    undecided = admin_parts - set(support.SCOPE_OF) - NEVER
    assert not undecided, f"decide a scope or add to NEVER: {sorted(undecided)}"
    assert not (set(support.SCOPE_OF) & NEVER)
    assert set(support.SCOPE_OF.values()) == {"content", "settings", "health", "members"}


@pytest.mark.parametrize(
    "blueprint,method,scopes,rw,allowed",
    [
        ("admin_news", "GET", ("content",), False, True),
        ("admin_news", "PUT", ("content",), False, False),
        ("admin_news", "PUT", ("content",), True, True),
        ("admin_news", "GET", ("settings",), True, False),
        ("admin_settings", "PATCH", ("settings",), True, True),
        ("admin_audit", "GET", ("health",), True, True),
        ("admin_audit", "DELETE", ("health",), True, False),  # a log is always read only
        ("admin_members", "GET", ("members",), True, True),
        ("admin_members", "POST", ("members",), True, False),  # members are always read only
        ("admin_payments", "GET", ("content", "settings", "health", "members"), True, False),
        ("settings", "GET", (), False, True),  # a public read
        ("contact", "POST", ("content",), True, False),  # a public write
    ],
)
def test_the_rule_of_what_a_session_may_do(blueprint, method, scopes, rw, allowed) -> None:
    ok, *_ = support.decide(blueprint, method, f"/api/x/{blueprint}", scopes, rw)
    assert ok is allowed
