"""Auth item G: data export, deleting a square and deleting the account (GDPR). No network: provider calls are replaced, the database is SQLite."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from flask import Flask
from sqlalchemy import select

from app.main import create_app
from app.platform import lifecycle
from app.platform.lifecycle import DestroyFailedError, ProviderRemovalFailedError, remove_provider_user
from app.platform.models import AuditLog, Membership, Organization, Square, SquareStatus, User
from app.platform.provisioning import LocalProvisioner, SupabaseApiError, SupabaseProvisioner
from app.providers.auth import FakeAuthProvider
from app.shared.db import Base
from tests.conftest import make_settings
from tests.staff_client import ADMIN, STAFF_HEADERS, staff_client

PREFIX = "/api/platform/v1"
HEADERS = {"X-Requested-With": "rootsquares"}
REF = "abcdefghijklmnopqrst"


def bearer(sub: str, email: str) -> dict[str, str]:
    return {**HEADERS, "Authorization": f"Bearer fake:{sub}:{email}"}


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    a = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'l.db'}", PROVISIONER="supabase", SUPABASE_ACCESS_TOKEN="pat", SUPABASE_ORG_SLUG="o"))
    Base.metadata.create_all(a.extensions["db_engine"]())
    a.extensions["providers"].auth = FakeAuthProvider()
    return a


def signed_up(app: Flask, sub: str, email: str, org: str = "Club") -> tuple[Any, dict[str, str], str]:
    c = app.test_client()
    h = bearer(sub, email)
    org_id = c.post(f"{PREFIX}/organizations", json={"name": org}, headers=h).json["organizations"][0]["id"]
    return c, h, org_id


def add_square(app: Flask, org_id: str, slug: str, status: str = "ready", ref: str | None = REF) -> str:
    with app.extensions["db_factory"]()() as db:
        sq = Square(
            org_id=uuid.UUID(org_id),
            name=slug.title(),
            slug=slug,
            theme_id="paper-brick",
            status=SquareStatus(status),
            provider_project_ref=ref,
            db_connection="SECRET-CONNECTION",
            provider_secrets="SECRET-KEYS",
        )
        db.add(sq)
        db.commit()
        return str(sq.id)


def audit_actions(app: Flask) -> list[str]:
    with app.extensions["db_factory"]()() as db:
        return list(db.scalars(select(AuditLog.action)))


# ---- export -----------------------------------------------------------------------------------------------------------------------
def test_export_holds_the_persons_data_and_no_secrets(app: Flask) -> None:
    c, h, org_id = signed_up(app, "u1", "asha@example.com")
    add_square(app, org_id, "first-org")
    r = c.get(f"{PREFIX}/me/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"] and r.headers["Cache-Control"] == "no-store"
    data = r.json
    assert data["account"]["email"] == "asha@example.com" and data["account"]["sign_in"] == "fake"
    assert [o["name"] for o in data["organizations"]] == ["Club"] and [s["slug"] for s in data["squares"]] == ["first-org"]
    assert any(a["action"] == "org.created" for a in data["activity"])
    text = json.dumps(data)
    for secret in ("SECRET-CONNECTION", "SECRET-KEYS", "password_hash", "db_connection", "provider_secrets"):
        assert secret not in text
    assert "account.export" in audit_actions(app)


def test_export_needs_a_sign_in(app: Flask) -> None:
    assert app.test_client().get(f"{PREFIX}/me/export").status_code == 401


def test_export_does_not_include_other_peoples_squares(app: Flask) -> None:
    c, h, _ = signed_up(app, "u1", "a@example.com")
    _, _, other_org = signed_up(app, "u2", "b@example.com", "Other")
    add_square(app, other_org, "theirs")
    assert c.get(f"{PREFIX}/me/export", headers=h).json["squares"] == []


# ---- deleting a square ------------------------------------------------------------------------------------------------------------
def test_deleting_a_square_removes_the_project_then_the_row(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    removed: list[str] = []
    monkeypatch.setattr(SupabaseProvisioner, "destroy_project", lambda self, ref: removed.append(ref) or True)
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    sq_id = add_square(app, org_id, "first-org")
    assert c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "wrong"}, headers=h).status_code == 422
    assert removed == []
    assert c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "First-Org"}, headers=h).status_code == 200
    assert removed == [REF] and c.get(f"{PREFIX}/squares/{sq_id}", headers=h).status_code == 404
    assert "square.deleted" in audit_actions(app)


def test_only_members_can_delete_and_not_while_provisioning(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SupabaseProvisioner, "destroy_project", lambda self, ref: True)
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    _, stranger, _ = signed_up(app, "u2", "b@example.com", "Other")
    sq_id = add_square(app, org_id, "first-org")
    assert c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "first-org"}, headers=stranger).status_code == 404
    busy = add_square(app, org_id, "busy-one", status="provisioning", ref=None)
    r = c.delete(f"{PREFIX}/squares/{busy}", json={"confirm_slug": "busy-one"}, headers=h)
    assert r.status_code == 409 and r.json["code"] == "still_provisioning"


def test_a_project_the_token_cannot_see_blocks_deletion_unless_an_admin_forces_it(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SupabaseProvisioner, "destroy_project", lambda self, ref: False)  # 404 at Supabase
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    sq_id = add_square(app, org_id, "first-org")
    r = c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "first-org"}, headers=h)
    assert r.status_code == 409 and r.json["code"] == "project_not_found"
    assert c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "first-org", "force": True}, headers=h).status_code == 403  # not staff
    forced = staff_client(app).delete(f"{ADMIN}/squares/{sq_id}", json={"confirm_slug": "first-org", "force": True}, headers=STAFF_HEADERS)
    assert forced.status_code == 200


def test_a_refused_provider_call_keeps_the_square(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: Any, ref: str) -> bool:
        raise SupabaseApiError("Supabase answered 403 to DELETE /v1/projects/x: Forbidden")

    monkeypatch.setattr(SupabaseProvisioner, "destroy_project", refuse)
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    sq_id = add_square(app, org_id, "first-org")
    r = c.delete(f"{PREFIX}/squares/{sq_id}", json={"confirm_slug": "first-org"}, headers=h)
    assert r.status_code == 502 and r.json["code"] == "destroy_failed" and "403" in r.json["detail"]
    assert c.get(f"{PREFIX}/squares/{sq_id}", headers=h).status_code == 200  # nothing was deleted
    assert "square.deleted" not in audit_actions(app)


def test_destroy_project_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    def make(status: int) -> SupabaseProvisioner:
        client = httpx.Client(base_url="https://api.supabase.com", transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"message": "x"})))
        return SupabaseProvisioner("pat", "o", "eu-west-1", client=client)

    assert make(200).destroy_project(REF) is True
    assert make(404).destroy_project(REF) is False
    with pytest.raises(SupabaseApiError, match="403"):
        make(403).destroy_project(REF)


def test_local_provisioner_only_drops_databases_it_made() -> None:
    local = LocalProvisioner("postgresql+psycopg://u:p@127.0.0.1:5432/x")
    for bad in ("postgres", "rootsquares_platform", "rs_sq_x", "rs_sq_first_org_ZZZZZZZZ", "rs_sq_a; drop database x_12345678"):
        with pytest.raises(RuntimeError, match="Refusing"):
            local.drop_database(bad)


def test_missing_tokens_are_reported_not_ignored() -> None:
    sq = Square(org_id=uuid.uuid4(), name="x", slug="x", theme_id="t", status=SquareStatus.READY, provider_project_ref=REF)
    with pytest.raises(DestroyFailedError, match="SUPABASE_ACCESS_TOKEN"):
        lifecycle.destroy_square_resources(make_settings(), sq)


# ---- deleting the account ----------------------------------------------------------------------------------------------------------
def test_wrong_address_deletes_nothing(app: Flask) -> None:
    c, h, _ = signed_up(app, "u1", "a@example.com")
    assert c.delete(f"{PREFIX}/me", json={"confirm_email": "other@example.com"}, headers=h).status_code == 422
    assert c.get(f"{PREFIX}/auth/me", headers=h).status_code == 200


def test_squares_must_be_deleted_before_the_account(app: Flask) -> None:
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    add_square(app, org_id, "first-org")
    r = c.delete(f"{PREFIX}/me", json={"confirm_email": "a@example.com"}, headers=h)
    assert r.status_code == 409 and r.json["code"] == "has_squares" and [s["slug"] for s in r.json["squares"]] == ["first-org"]
    with app.extensions["db_factory"]()() as db:
        assert db.scalar(select(User.id).where(User.email == "a@example.com")) is not None


def test_the_account_its_organisation_and_its_logins_are_deleted(app: Flask) -> None:
    c, h, org_id = signed_up(app, "u1", "a@example.com")
    r = c.delete(f"{PREFIX}/me", json={"confirm_email": "A@Example.com"}, headers=h)
    assert r.status_code == 200 and r.json["provider_account_removed"] is False  # fake provider, no AUTH_ADMIN_KEY: the answer says so
    with app.extensions["db_factory"]()() as db:
        assert db.scalar(select(User.id).where(User.email == "a@example.com")) is None
        assert db.get(Organization, uuid.UUID(org_id)) is None and db.scalar(select(Membership.id)) is None
        rows = list(db.scalars(select(AuditLog)))
        assert all(x.actor_user_id is None for x in rows)  # the history stays, the person does not
        assert "account.deleted" in [x.action for x in rows]


def test_password_accounts_and_their_cookies_are_deleted_too(app: Flask) -> None:
    c = app.test_client()
    body = {"email": "pw@example.com", "password": "correct-horse-1", "name": "P", "organization_name": "Club"}
    assert c.post(f"{PREFIX}/auth/signup", json=body, headers=HEADERS).status_code == 201
    r = c.delete(f"{PREFIX}/me", json={"confirm_email": "pw@example.com"}, headers=HEADERS)
    assert r.status_code == 200 and r.json["provider_account_removed"] is True  # nothing lives at a provider
    assert c.get(f"{PREFIX}/auth/me").status_code == 401
    assert c.post(f"{PREFIX}/auth/login", json={"email": "pw@example.com", "password": "correct-horse-1"}, headers=HEADERS).status_code == 401


def test_the_provider_account_is_removed_when_a_service_key_is_set() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(method=request.method, url=str(request.url), headers=request.headers)
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    s = make_settings(AUTH_PROVIDER="supabase", AUTH_URL="https://abc.supabase.co", AUTH_ADMIN_KEY="service.jwt")
    user = User(email="a@example.com", name="", auth_user_id="uid-1", auth_provider="supabase")
    assert remove_provider_user(s, user, client) is True
    assert seen["method"] == "DELETE" and seen["url"] == "https://abc.supabase.co/auth/v1/admin/users/uid-1"
    assert seen["headers"]["apikey"] == "service.jwt" and seen["headers"]["authorization"] == "Bearer service.jwt"
    assert remove_provider_user(make_settings(AUTH_PROVIDER="supabase", AUTH_URL="https://abc.supabase.co"), user, client) is False  # no key
    assert remove_provider_user(s, User(email="p@example.com", name=""), client) is True  # password account


def test_a_failing_provider_stops_the_deletion_before_anything_changes(tmp_path: Path) -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    s = make_settings(AUTH_PROVIDER="supabase", AUTH_URL="https://abc.supabase.co", AUTH_ADMIN_KEY="k")
    with pytest.raises(ProviderRemovalFailedError):
        remove_provider_user(s, User(email="a@example.com", name="", auth_user_id="u", auth_provider="supabase"), client)


# ---- the public hello-world data of a square -------------------------------------------------------------------------------------------
def test_a_ready_square_has_a_public_page_without_secrets(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.platform.routes as routes

    monkeypatch.setattr(routes, "square_database_check", lambda settings, sq: {"ok": True, "admins": 1})
    c, _, org_id = signed_up(app, "u1", "a@example.com")
    add_square(app, org_id, "first-org")
    add_square(app, org_id, "busy-one", status="provisioning", ref=None)
    anonymous = app.test_client()
    r = anonymous.get(f"{PREFIX}/public/squares/First-Org")
    assert r.status_code == 200
    assert r.json == {
        "name": "First-Org",
        "slug": "first-org",
        "theme_id": "paper-brick",
        "domain": "",
        "google_login": "requested",
        "has_auth_project": True,
        "database": {"ok": True, "admins": 1},
        "auth_url": None,
        "auth_public_key": None,
        "theme_overrides": None,
    }
    for text in ("SECRET", "a@example.com", REF):
        assert text not in json.dumps(r.json)
    assert anonymous.get(f"{PREFIX}/public/squares/busy-one").status_code == 404  # not ready
    assert anonymous.get(f"{PREFIX}/public/squares/nope").status_code == 404


def test_the_database_check_survives_an_unreachable_database() -> None:
    from app.platform.public import square_database_check
    from app.shared.crypto import Encryptor

    s = make_settings()
    sq = Square(org_id=uuid.uuid4(), name="x", slug="x", theme_id="t", status=SquareStatus.READY)
    assert square_database_check(s, sq) == {"ok": False}  # no connection stored
    sq.db_connection = Encryptor(s.fernet_key).encrypt("postgresql+psycopg://u:p@127.0.0.1:1/x")  # nothing listens on port 1
    assert square_database_check(s, sq) == {"ok": False}


# ---- signing in to the square itself ---------------------------------------------------------------------------------------------------
def real_square(app: Flask, org_id: str, slug: str = "first-org") -> str:
    """A ready square with properly encrypted connection and keys, as the provisioner stores them."""
    from app.shared.crypto import Encryptor

    enc = Encryptor(app.extensions["settings"].fernet_key)
    secrets = {"project_url": "https://abc.supabase.co", "publishable": "sb_publishable_x", "service_role": "SERVICE-KEY", "anon": "anon.jwt"}
    with app.extensions["db_factory"]()() as db:
        sq = Square(
            org_id=uuid.UUID(org_id),
            name="First",
            slug=slug,
            theme_id="paper-brick",
            status=SquareStatus.READY,
            provider="supabase",
            provider_project_ref=REF,
            db_connection=enc.encrypt("postgresql+psycopg://u:p@h/db"),
            provider_secrets=enc.encrypt(json.dumps(secrets)),
        )
        db.add(sq)
        db.commit()
        return str(sq.id)


def test_the_public_page_hands_out_only_the_public_sign_in_settings(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.platform.routes as routes

    monkeypatch.setattr(routes, "square_database_check", lambda settings, sq: {"ok": True, "admins": 1})
    _, _, org_id = signed_up(app, "u1", "a@example.com")
    real_square(app, org_id)
    data = app.test_client().get(f"{PREFIX}/public/squares/first-org").json
    assert data["auth_url"] == "https://abc.supabase.co" and data["auth_public_key"] == "sb_publishable_x"
    assert "SERVICE-KEY" not in json.dumps(data)  # the service key never leaves the platform


def test_a_token_of_the_square_shows_who_and_what_role(app: Flask) -> None:
    from app.platform.square_verifier import SquareAdmin, SquareAuthVerifier

    _, _, org_id = signed_up(app, "u1", "a@example.com")
    real_square(app, org_id)
    app.extensions["square_auth"] = SquareAuthVerifier(
        app.extensions["db_factory"],
        app.extensions["settings"],
        provider_factory=lambda provider, secrets: FakeAuthProvider(),
        admin_lookup=lambda url, sub: SquareAdmin(id="1", email="o@example.com", name="O", role="owner") if sub == "owner-1" else None,
    )
    c = app.test_client()
    assert c.get(f"{PREFIX}/public/squares/first-org/me").status_code == 401  # no token
    assert c.get(f"{PREFIX}/public/squares/first-org/me", headers={"Authorization": "Bearer nonsense"}).json["code"] == "invalid_token"
    admin = c.get(f"{PREFIX}/public/squares/first-org/me", headers={"Authorization": "Bearer fake:owner-1:o@example.com"}).json
    assert admin == {"email": "o@example.com", "name": "", "role": "owner", "is_admin": True}
    member = c.get(f"{PREFIX}/public/squares/first-org/me", headers={"Authorization": "Bearer fake:visitor-2:v@example.com"}).json
    assert member["is_admin"] is False and member["role"] is None
    assert c.get(f"{PREFIX}/public/squares/nope/me", headers={"Authorization": "Bearer fake:owner-1:o@example.com"}).status_code == 404


def test_new_squares_allow_the_local_site_to_receive_the_sign_in() -> None:
    assert make_settings(ENV="local").square_extra_redirects == [
        "http://localhost:5273/**",
        "http://{slug}.localhost:5273/**",
        "http://{slug}.localhost:5274/**",  # the square app (square/frontend)
    ]
    assert make_settings(ENV="test").square_extra_redirects == []
    assert make_settings(SQUARE_EXTRA_REDIRECT_URLS="https://a.example/**, https://b.example/**").square_extra_redirects == [
        "https://a.example/**",
        "https://b.example/**",
    ]


# ---- which square is served on this host --------------------------------------------------------------------------------------------
def test_a_square_is_found_by_its_host_name(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.platform.routes as routes

    monkeypatch.setattr(routes, "square_database_check", lambda settings, sq: {"ok": True, "admins": 1})
    _, _, org_id = signed_up(app, "u1", "a@example.com")
    add_square(app, org_id, "first-org")
    with app.extensions["db_factory"]()() as db:
        sq = db.scalar(select(Square).where(Square.slug == "first-org"))
        assert sq is not None
        sq.domain = "www.bca-test.org"  # a custom domain
        db.commit()
    c = app.test_client()
    assert c.get(f"{PREFIX}/public/hosts/www.bca-test.org").json["slug"] == "first-org"
    assert c.get(f"{PREFIX}/public/hosts/WWW.BCA-TEST.ORG:443").json["slug"] == "first-org"  # case and port do not matter
    assert c.get(f"{PREFIX}/public/hosts/first-org.localhost:5273").json["slug"] == "first-org"  # developer machines
    assert c.get(f"{PREFIX}/public/hosts/other.localhost").status_code == 404
    assert c.get(f"{PREFIX}/public/hosts/evil.example.com").status_code == 404


def test_public_data_answers_any_origin_without_credentials_and_the_rest_does_not() -> None:
    app = create_app(make_settings(CORS_ORIGINS="http://localhost:5273"))
    c = app.test_client()
    pre = {"Origin": "http://first-org.localhost:5273", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    r = c.options(f"{PREFIX}/public/squares/x/me", headers=pre)
    assert r.headers["Access-Control-Allow-Origin"] in ("*", pre["Origin"]) and "authorization" in r.headers["Access-Control-Allow-Headers"].lower()
    assert "Access-Control-Allow-Credentials" not in r.headers
    other = c.options(f"{PREFIX}/auth/me", headers=pre)
    assert "Access-Control-Allow-Origin" not in other.headers  # the platform API stays closed to square sites
    own = c.options(f"{PREFIX}/auth/me", headers={**pre, "Origin": "http://localhost:5273"})
    assert own.headers["Access-Control-Allow-Origin"] == "http://localhost:5273" and own.headers["Access-Control-Allow-Credentials"] == "true"
