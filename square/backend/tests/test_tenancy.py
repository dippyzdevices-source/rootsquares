"""Many squares from one server (rootsquares W6-R26): the host name picks the square's own database and sign-in project.

A fake platform database (sqlite, only the `squares` table) and two fake square databases (sqlite, the real BCA tables) stand in for the real ones.
"""

import base64
import hashlib
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.modules import MODULE_KEYS
from app.settings.models import SiteSettings
from tests.auth_helpers import FakeJWKClient, auth_header, make_token

DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()).decode()
FERNET = Fernet(DEV_KEY.encode())


def _enc(value: str) -> str:
    return FERNET.encrypt(value.encode()).decode()


def _square_db(path: Path, contact_email: str, owner_sub: str | None = None) -> str:
    """A square's own database: the BCA tables, one settings row, and (if given) the platform's `admins` row for the owner."""
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")  # single-tenant app, only to get the model metadata registered
    with app.app_context():
        db.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(SiteSettings(id=1, contact_email=contact_email, contact_phone="", contact_address=""))
        s.commit()
    if owner_sub:
        with engine.begin() as conn:
            conn.execute(text("create table admins (id text primary key, email text, auth_user_id text, role text)"))
            conn.execute(text("insert into admins values ('1', 'owner@example.org', :sub, 'owner')"), {"sub": owner_sub})
    engine.dispose()
    return url


@pytest.fixture
def server(tmp_path: Path):
    owner_sub = str(uuid.uuid4())
    url_a = _square_db(tmp_path / "a.db", "a@example.org", owner_sub)
    url_b = _square_db(tmp_path / "b.db", "b@example.org")
    platform_url = f"sqlite:///{tmp_path / 'platform.db'}"
    platform = create_engine(platform_url)
    with platform.begin() as conn:
        conn.execute(
            text(
                "create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, "
                "db_connection text, provider_secrets text)"
            )
        )
        rows = [
            ("square-a", "Square A", "paper-brick", "square-a.rootsquares.com", "ready", None, url_a, {"project_url": "https://a.supabase.co", "publishable": "pk-a"}),
            ("square-b", "Square B", "paper-brick", "club-b.example.org", "ready", None, url_b, {"project_url": "https://b.supabase.co", "publishable": "pk-b"}),
            ("square-c", "Square C", "paper-brick", "square-c.rootsquares.com", "provisioning", None, url_a, {}),
            ("square-d", "Square D", "paper-brick", "square-d.rootsquares.com", "ready", "2026-10-01", url_a, {}),
        ]
        for slug, name, theme, domain, status, suspended, url, secrets in rows:
            conn.execute(
                text("insert into squares values (:slug, :name, :theme, :domain, :status, :susp, :url, :sec)"),
                {"slug": slug, "name": name, "theme": theme, "domain": domain, "status": status, "susp": suspended, "url": _enc(url), "sec": _enc(json.dumps(secrets))},
            )
    platform.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url):
        app = create_app("testing")
    return app, owner_sub


def test_each_host_gets_its_own_squares_database(server):
    app, _ = server
    c = app.test_client()
    a = c.get("/api/settings", base_url="http://square-a.localhost").get_json()
    b = c.get("/api/settings", base_url="http://square-b.localhost:5274").get_json()  # the port is ignored
    assert a["contact_email"] == "a@example.org"
    assert b["contact_email"] == "b@example.org"


def test_a_custom_domain_finds_its_square(server):
    app, _ = server
    got = app.test_client().get("/api/settings", base_url="https://club-b.example.org").get_json()
    assert got["contact_email"] == "b@example.org"
    got = app.test_client().get("/api/settings", base_url="https://square-a.rootsquares.com").get_json()
    assert got["contact_email"] == "a@example.org"


@pytest.mark.parametrize("host", ["nobody.localhost", "square-c.localhost", "square-d.localhost", "example.com", "localhost"])
def test_unknown_unready_or_suspended_squares_are_404(server, host):
    app, _ = server
    response = app.test_client().get("/api/settings", base_url=f"http://{host}")
    assert response.status_code == 404 and response.get_json() == {"error": "Unknown square"}


def test_health_does_not_need_a_square(server):
    app, _ = server
    assert app.test_client().get("/api/health", base_url="http://nobody.localhost").status_code == 200


def test_square_config_gives_only_public_sign_in_settings(server):
    app, _ = server
    response = app.test_client().get("/api/square/config", base_url="http://square-a.localhost")
    body = response.get_json()
    assert body == {"own_mail_domain": False, "platform_url": "", "google_login": True, "analytics": False, "slug": "square-a", "name": "Square A", "theme_id": "paper-brick", "theme_overrides": None,"currency": "NOK", "phone": {"country": "NO", "name": "Norway", "dial": "47", "min_digits": 8, "max_digits": 8, "trunk_zero": False}, "logo_url": "", "logo_dark_url": "", "group_type": "", "modules": list(MODULE_KEYS), "features": ["message_reminders", "repeating_events"], "sleeping": False, "event_pass": None, "sleep_contact": {}, "auth": {"provider": "supabase", "url": "https://a.supabase.co", "public_key": "pk-a"}}
    text_body = response.get_data(as_text=True)
    assert "sqlite" not in text_body and "db_connection" not in text_body


def test_the_squares_owner_is_an_admin_and_nobody_else_is(server):
    app, owner_sub = server
    c = app.test_client()
    iss_a, iss_b = "https://a.supabase.co/auth/v1", "https://b.supabase.co/auth/v1"  # each square's own sign-in project issues its own tokens
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        owner = c.get("/api/auth/me", base_url="http://square-a.localhost", headers=auth_header(make_token(sub=owner_sub, email="owner@example.org", iss=iss_a)))
        visitor = c.get("/api/auth/me", base_url="http://square-a.localhost", headers=auth_header(make_token(sub=str(uuid.uuid4()), email="v@example.org", iss=iss_a)))
        # the same sign-in id in another square's project has no rights there
        elsewhere = c.get("/api/auth/me", base_url="http://square-b.localhost", headers=auth_header(make_token(sub=owner_sub, email="owner@example.org", iss=iss_b)))
    assert owner.get_json()["role"] == "admin"
    assert visitor.get_json()["role"] == "member"
    assert elsewhere.get_json()["role"] == "member"


def test_a_token_of_one_square_is_refused_by_another_square(server):
    app, owner_sub = server
    token = make_token(sub=owner_sub, email="owner@example.org", iss="https://a.supabase.co/auth/v1")  # issued by square A's sign-in project
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        at_b = app.test_client().get("/api/auth/me", base_url="http://square-b.localhost", headers=auth_header(token))
    assert at_b.status_code == 401


def test_the_owners_own_colours_and_fonts_reach_the_config(server):
    """W18-R18: a platform database with the theme_overrides column gives the square its owner's look; damaged text means the theme as designed."""
    app, _ = server
    platform = create_engine(app.config["PLATFORM_DATABASE_URL"])
    with platform.begin() as conn:
        for column in ("currency", "phone_country", "logo_url", "logo_dark_url", "modules", "running_plan", "sleep_state", "sleep_contact", "launch_package",
                       "event_live_until", "event_archive_until", "group_type", "theme_overrides"):  # the newest platform database has them all
            conn.execute(text(f"alter table squares add column {column} text"))
        look = {"colors": {"bg": "#f6f1e7", "ink": "#2b2a28", "acc": "#c2410c"}, "fonts": "soft", "spinners": ["diya", "kite"]}
        conn.execute(text("update squares set theme_overrides = :v where slug = 'square-a'"), {"v": json.dumps(look)})
        conn.execute(text("update squares set theme_overrides = '{not json' where slug = 'square-b'"))
    platform.dispose()
    c = app.test_client()
    assert c.get("/api/square/config", base_url="http://square-a.localhost").get_json()["theme_overrides"] == look
    assert c.get("/api/square/config", base_url="http://square-b.localhost").get_json()["theme_overrides"] is None


def test_the_shared_draft_is_hidden_from_the_config_and_given_only_for_the_token(server):
    """W18-R47: the draft sits beside the live look in the same column; the config never shows it, the draft endpoint needs the token (and the passcode, if set)."""
    from datetime import datetime, timedelta, timezone

    from werkzeug.security import generate_password_hash

    from app import tenancy

    app, _ = server
    platform = create_engine(app.config["PLATFORM_DATABASE_URL"])
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    live = {"fonts": "soft"}
    a = {**live, "draft": {"look": {"fonts": "bold"}, "theme_id": "pearl", "token": "tok-a", "expires_at": soon, "passcode_hash": generate_password_hash("garden")}}
    b = {"draft": {"look": {"fonts": "bold"}, "token": "tok-b", "expires_at": past}}
    with platform.begin() as conn:
        for column in ("currency", "phone_country", "logo_url", "logo_dark_url", "modules", "running_plan", "sleep_state", "sleep_contact", "launch_package",
                       "event_live_until", "event_archive_until", "group_type", "theme_overrides"):
            conn.execute(text(f"alter table squares add column {column} text"))
        conn.execute(text("update squares set theme_overrides = :v where slug = 'square-a'"), {"v": json.dumps(a)})
        conn.execute(text("update squares set theme_overrides = :v where slug = 'square-b'"), {"v": json.dumps(b)})
    platform.dispose()
    c = app.test_client()
    base = "http://square-a.localhost"
    assert c.get("/api/square/config", base_url=base).get_json()["theme_overrides"] == live  # no draft, no token, no hash in the config
    assert "tok-a" not in c.get("/api/square/config", base_url=base).get_data(as_text=True)
    assert c.get("/api/square/config", base_url="http://square-b.localhost").get_json()["theme_overrides"] is None
    ask = lambda **body: c.post("/api/square/look-draft", json=body, base_url=base)  # noqa: E731
    assert ask(token="nope").status_code == 403
    assert ask(token="tok-a").status_code == 401 and ask(token="tok-a").get_json()["error"] == "passcode_required"
    assert ask(token="tok-a", passcode="wrong").status_code == 403
    ok = ask(token="tok-a", passcode="garden")
    assert ok.status_code == 200 and ok.get_json() == {"look": {"fonts": "bold"}, "theme_id": "pearl"}
    assert c.post("/api/square/look-draft", json={"token": "tok-b"}, base_url="http://square-b.localhost").status_code == 410  # expired
    tenancy._DRAFT_FAILS.clear()
    for _ in range(tenancy.DRAFT_FAIL_LIMIT):
        ask(token="guess")
    assert ask(token="tok-a", passcode="garden").status_code == 429  # too many wrong tries
    tenancy._DRAFT_FAILS.clear()


def test_a_season_that_is_on_wears_its_own_theme_and_look_and_the_others_stay_hidden(server):
    """W18-R49: the config shows the live look, or the look of the first season that covers today; the list itself never reaches the browser."""
    from datetime import date

    from app import tenancy

    today = date(2026, 11, 1)
    once = {"id": "aaaaaa", "name": "Diwali", "start": "2026-10-28", "end": "2026-11-12", "yearly": False, "theme_id": "pearl", "look": {"fonts": "bold"}}
    yearly = {"id": "bbbbbb", "name": "Christmas", "start": "2026-12-20", "end": "2027-01-05", "yearly": True, "look": {"fonts": "elegant"}}
    assert tenancy.season_covers(once, today) and not tenancy.season_covers(once, date(2026, 11, 13)) and not tenancy.season_covers(once, date(2027, 11, 1))
    assert tenancy.season_covers(yearly, date(2031, 1, 2)) and tenancy.season_covers(yearly, date(2029, 12, 25)) and not tenancy.season_covers(yearly, date(2031, 1, 6))
    assert tenancy.season_covers({"start": "bad", "end": "2026-01-01"}, today) is False
    assert tenancy.active_season((yearly, once), today) is once and tenancy.active_season((yearly,), today) is None

    app, _ = server
    platform = create_engine(app.config["PLATFORM_DATABASE_URL"])
    wide = {"id": "cccccc", "name": "All year", "start": "2000-01-01", "end": "2000-12-31", "yearly": True, "theme_id": "pearl", "look": {"fonts": "bold"}}
    never = {**wide, "id": "dddddd", "start": "2000-01-01", "end": "2000-01-01"}
    live = {"fonts": "soft", "seasons": [never]}
    with platform.begin() as conn:
        for column in ("currency", "phone_country", "logo_url", "logo_dark_url", "modules", "running_plan", "sleep_state", "sleep_contact", "launch_package",
                       "event_live_until", "event_archive_until", "group_type", "theme_overrides"):
            conn.execute(text(f"alter table squares add column {column} text"))
        conn.execute(text("update squares set theme_overrides = :v where slug = 'square-a'"), {"v": json.dumps(live)})
        conn.execute(text("update squares set theme_overrides = :v where slug = 'square-b'"), {"v": json.dumps({"fonts": "soft", "seasons": [wide]})})
    platform.dispose()
    c = app.test_client()
    # square-a has a season that is not on (1 January only): the live look and theme; the hidden list is not in the answer
    quiet = c.get("/api/square/config", base_url="http://square-a.localhost").get_json()
    assert quiet["theme_overrides"] == {"fonts": "soft"} and quiet["theme_id"] == "paper-brick" and "seasons" not in json.dumps(quiet)
    # square-b has a season that covers every day: its theme and look
    on = c.get("/api/square/config", base_url="http://square-b.localhost").get_json()
    assert on["theme_overrides"] == {"fonts": "bold"} and on["theme_id"] == "pearl" and "seasons" not in json.dumps(on)


def test_a_square_own_website_domain_is_served_only_while_the_package_has_it(tmp_path: Path):
    """ADR 098: platform `squares.site_domain` names a host that serves the square; a lower package or an unready square does not serve it."""
    url = _square_db(tmp_path / "own.db", "own@example.org")
    platform_url = f"sqlite:///{tmp_path / 'platform_own.db'}"
    platform = create_engine(platform_url)
    with platform.begin() as conn:
        conn.execute(
            text(
                "create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, db_connection text, "
                "provider_secrets text, launch_package text, site_domain text)"
            )
        )
        rows = [
            ("own-grove", "grove", "www.grove.example.org", "ready"),
            ("own-old", None, "www.old.example.org", "ready"),
            ("own-lower", "square", "www.lower.example.org", "ready"),
            ("own-unready", "grove", "www.unready.example.org", "provisioning"),
        ]
        for slug, package, own, status in rows:
            conn.execute(
                text("insert into squares values (:slug, :slug, 'paper-brick', :domain, :status, null, :url, :sec, :pkg, :own)"),
                {"slug": slug, "domain": f"{slug}.rootsquares.com", "status": status, "url": _enc(url), "sec": _enc("{}"), "pkg": package, "own": own},
            )
    platform.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url):
        app = create_app("testing")
    c = app.test_client()
    for host in ("www.grove.example.org", "www.old.example.org", "own-grove.rootsquares.com"):
        assert c.get("/api/settings", base_url=f"https://{host}").get_json()["contact_email"] == "own@example.org", host
    for host in ("www.lower.example.org", "www.unready.example.org", "www.nobody.example.org"):
        assert c.get("/api/settings", base_url=f"https://{host}").status_code == 404, host


def test_the_config_hands_the_browser_the_platform_address_only_when_it_is_a_web_address(server):
    """W26-R17: PLATFORM_SITE_URL lets a locked feature link to the platform; anything that is not an http(s) address is never handed out."""
    app, _ = server
    c = app.test_client()
    for value, expected in (("https://rootsquares.example/", "https://rootsquares.example"), ("", ""), ("javascript:alert(1)", "")):
        app.config["PLATFORM_SITE_URL"] = value
        got = c.get("/api/square/config", base_url="http://square-a.localhost").get_json()
        assert got["platform_url"] == expected, value
