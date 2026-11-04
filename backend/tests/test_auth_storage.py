"""ADR 028: auth providers (Supabase, Neon, fake), bearer sign-in next to the cookie login, storage providers and the settings rules.
No network: signing keys are generated here and the JWKS lookup is replaced; the route tests use a throwaway SQLite file."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from flask import Flask
from pydantic import ValidationError

from app.main import create_app
from app.platform.models import AuditLog
from app.providers.auth import FakeAuthProvider, NeonAuthProvider, SupabaseAuthProvider, build_auth_provider
from app.providers.storage import FakeStorage, S3CompatibleStorage, build_storage
from app.shared.crypto import hash_password
from app.shared.db import Base
from tests.conftest import make_settings
from tests.price_seed import seed_prices
from tests.staff_client import as_admin

PREFIX = "/api/platform/v1"
ISS = "https://x.supabase.co/auth/v1"
HEADERS = {"X-Requested-With": "rootsquares"}


class FakeJwks:
    def __init__(self, key: Any) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, _token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self._key.public_key())


def _token(key: Any, alg: str, **claims: Any) -> str:
    payload = {"sub": "u-1", "email": "a@example.com", "exp": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5), **claims}
    return jwt.encode(payload, key, algorithm=alg)


# ---- providers ---------------------------------------------------------------------------------------------------------------------
def test_supabase_token_is_verified_and_audience_checked() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    provider = SupabaseAuthProvider("https://x.supabase.co/", FakeJwks(key))  # type: ignore[arg-type]
    ok = provider.verify(_token(key, "ES256", aud="authenticated", iss=ISS, user_metadata={"full_name": "Asha Roy"}))
    assert ok == {"sub": "u-1", "email": "a@example.com", "name": "Asha Roy"}
    with pytest.raises(jwt.PyJWTError):
        provider.verify(_token(key, "ES256", aud="someone-else"))
    with pytest.raises(jwt.PyJWTError):
        provider.verify(_token(key, "ES256", aud="authenticated", iss=ISS, exp=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)))
    with pytest.raises(jwt.PyJWTError):  # signed with another key
        provider.verify(_token(ec.generate_private_key(ec.SECP256R1()), "ES256", aud="authenticated", iss=ISS))
    with pytest.raises(jwt.PyJWTError):  # a token of ANOTHER Supabase project, even if its keys were the same
        provider.verify(_token(key, "ES256", aud="authenticated", iss="https://other.supabase.co/auth/v1"))
    with pytest.raises(jwt.PyJWTError):  # no issuer at all
        provider.verify(_token(key, "ES256", aud="authenticated"))


def test_neon_token_needs_the_auth_origin_as_issuer_and_audience() -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    provider = NeonAuthProvider("https://ep-1.aws.neon.tech/neondb/auth", FakeJwks(key))  # type: ignore[arg-type]
    origin = "https://ep-1.aws.neon.tech"
    assert provider.verify(_token(key, "EdDSA", iss=origin, aud=origin))["sub"] == "u-1"
    with pytest.raises(jwt.PyJWTError):
        provider.verify(_token(key, "EdDSA", iss="https://evil.example", aud=origin))
    with pytest.raises(jwt.PyJWTError):
        provider.verify(_token(key, "EdDSA", iss=origin, aud="https://evil.example"))


def test_jwks_urls() -> None:
    assert SupabaseAuthProvider("https://x.supabase.co/")._jwks_url == "https://x.supabase.co/auth/v1/.well-known/jwks.json"
    assert NeonAuthProvider("https://ep-1.aws.neon.tech/neondb/auth/")._jwks_url == "https://ep-1.aws.neon.tech/neondb/auth/.well-known/jwks.json"


def test_fake_provider_and_factory() -> None:
    assert FakeAuthProvider().verify("fake:u9:b@example.com")["email"] == "b@example.com"
    for bad in ("", "fake::x", "real:u9:b@example.com", "fake:only"):
        with pytest.raises(jwt.PyJWTError):
            FakeAuthProvider().verify(bad)
    assert build_auth_provider(make_settings()) is None
    assert isinstance(build_auth_provider(make_settings(AUTH_PROVIDER="supabase", AUTH_URL="https://x.supabase.co")), SupabaseAuthProvider)
    assert isinstance(build_auth_provider(make_settings(AUTH_PROVIDER="neon", AUTH_URL="https://ep.neon.tech/db/auth")), NeonAuthProvider)


# ---- storage -----------------------------------------------------------------------------------------------------------------------
def test_fake_storage_round_trip() -> None:
    s = FakeStorage()
    s.upload("a/b.png", b"x", "image/png")
    url = s.url_for("a/b.png")
    assert s.key_from_url(url) == "a/b.png" and s.key_from_url("https://other/x") is None
    s.delete("a/b.png")
    assert s.objects == {}


def test_s3_storage_urls() -> None:
    kwargs = {"endpoint_url": "https://s3.example.com/storage/v1/s3", "access_key": "k", "secret_key": "s", "region": "eu-central-1"}
    public = S3CompatibleStorage(bucket="pub", public=True, public_base_url="https://cdn.example.com/pub/", **kwargs)
    assert public.url_for("g/1.webp") == "https://cdn.example.com/pub/g/1.webp"
    assert public.key_from_url("https://cdn.example.com/pub/g/1.webp") == "g/1.webp" and public.key_from_url("https://x/g/1.webp") is None
    private = S3CompatibleStorage(bucket="priv", public=False, **kwargs)
    url = private.url_for("r/receipt.pdf")
    assert "/priv/r/receipt.pdf" in url and "X-Amz-Signature" in url  # path-style, presigned
    assert private.key_from_url(url) is None


def test_storage_factory_uses_fakes_without_endpoint_and_s3_with_one() -> None:
    pub, priv = build_storage(make_settings())
    assert isinstance(pub, FakeStorage) and isinstance(priv, FakeStorage)
    pub, priv = build_storage(
        make_settings(
            STORAGE_S3_ENDPOINT_URL="https://s3.example.com",
            STORAGE_S3_ACCESS_KEY="k",
            STORAGE_S3_SECRET_KEY="s",
            STORAGE_PUBLIC_BASE_URL="https://cdn.example.com",
        )
    )
    assert isinstance(pub, S3CompatibleStorage) and isinstance(priv, S3CompatibleStorage)


# ---- settings rules ----------------------------------------------------------------------------------------------------------------
PROD = {
    "ENV": "production",
    "JWT_SECRET": "x" * 40,
    "FERNET_KEY": "k",
    "DATABASE_URL": "postgresql+psycopg://u:p@h/db",
    "COOKIE_SECURE": True,
    "ADMIN_ORIGINS": "https://admin.example.com",
    "API_SURFACE": "admin",  # production runs a customer service and an admin service (ADR 084); the rules of each are in test_api_surface.py
    "STAFF_JWT_SECRET": "t" * 40,
    "STAFF_FERNET_KEY": "sk",
    "SUPPORT_SESSION_KEY": "u" * 40,  # the admin service signs support sessions with its own key (ADR 089)
    "PROVISIONER": "neon",
    "NEON_API_KEY": "k",
    "AUTH_PROVIDER": "neon",
    "AUTH_URL": "https://ep.neon.tech/db/auth",
    "STORAGE_S3_ENDPOINT_URL": "https://s3.example.com",
    "STORAGE_S3_ACCESS_KEY": "k",
    "STORAGE_S3_SECRET_KEY": "s",
    "STORAGE_PUBLIC_BASE_URL": "https://cdn.example.com",
    "BILLING_PROVIDER": "stripe",
    "STRIPE_SECRET_KEY": "k",
    "STRIPE_WEBHOOK_SECRET": "w",
}


def _prod(**changes: object) -> object:
    from app.shared.config import Settings

    return Settings(_env_file=None, **{**PROD, **changes})  # type: ignore[call-arg]


def test_provider_needs_a_url() -> None:
    with pytest.raises(ValidationError, match="AUTH_URL"):
        make_settings(AUTH_PROVIDER="supabase")


def test_production_needs_neon_auth_and_real_storage() -> None:
    _prod()
    with pytest.raises(ValidationError, match="ADMIN_ORIGINS"):
        _prod(ADMIN_ORIGINS="")
    with pytest.raises(ValidationError, match="customer origin"):
        _prod(CORS_ORIGINS="https://admin.example.com")
    with pytest.raises(ValidationError, match="must be neon"):
        _prod(AUTH_PROVIDER="supabase")
    with pytest.raises(ValidationError, match="must be neon"):
        _prod(AUTH_PROVIDER="", AUTH_URL="")
    with pytest.raises(ValidationError, match="STORAGE_S3_ENDPOINT_URL"):
        _prod(STORAGE_S3_ENDPOINT_URL="")


# ---- bearer sign-in next to the cookie login ---------------------------------------------------------------------------------------
@pytest.fixture
def api(tmp_path: Path) -> Flask:
    app = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'platform.db'}"))
    Base.metadata.create_all(app.extensions["db_engine"]())
    app.extensions["providers"].auth = FakeAuthProvider()
    seed_prices(app)  # test data: the application holds no price (W14-R29)
    return app


def test_bearer_token_signs_in_and_creates_the_user_once(api: Flask) -> None:
    c = api.test_client()
    first = c.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer fake:u-1:Asha@Example.com"})
    assert first.status_code == 200 and first.json["email"] == "asha@example.com" and first.json["organizations"] == []
    again = c.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer fake:u-1:asha@example.com"})
    assert again.json["id"] == first.json["id"]


def test_bad_or_missing_bearer_is_401(api: Flask) -> None:
    c = api.test_client()
    assert c.get(f"{PREFIX}/auth/me").status_code == 401
    assert c.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert c.get(f"{PREFIX}/auth/me", headers={"Authorization": "Basic fake:u-1:a@example.com"}).status_code == 401


def test_bearer_is_ignored_when_no_provider_is_configured(api: Flask) -> None:
    api.extensions["providers"].auth = None
    assert api.test_client().get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer fake:u-1:a@example.com"}).status_code == 401


def test_a_token_cannot_take_over_an_existing_password_account(api: Flask) -> None:
    c = api.test_client()
    signup = {"email": "owner@example.com", "password": "correct-horse-1", "name": "Owner", "organization_name": "Club"}
    assert c.post(f"{PREFIX}/auth/signup", json=signup, headers=HEADERS).status_code == 201
    c2 = api.test_client()
    r = c2.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer fake:other:owner@example.com"})
    assert r.status_code == 409 and r.json["code"] == "account_exists"


def test_provider_only_account_cannot_use_password_login(api: Flask) -> None:
    c = api.test_client()
    c.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer fake:u-2:nopw@example.com"})
    r = c.post(f"{PREFIX}/auth/login", json={"email": "nopw@example.com", "password": hash_password("x")[:12] + "abcdefgh"}, headers=HEADERS)
    assert r.status_code == 401 and r.json["code"] == "invalid_credentials"


def test_cors_preflight_allows_the_authorization_header() -> None:
    app = create_app(make_settings(CORS_ORIGINS="http://localhost:5273"))
    preflight = {"Origin": "http://localhost:5273", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    r = app.test_client().options(f"{PREFIX}/auth/me", headers=preflight)
    assert r.status_code == 200 and "authorization" in r.headers.get("Access-Control-Allow-Headers", "").lower()


# ---- organization onboarding for provider users -----------------------------------------------------------------------------------
def test_provider_user_creates_an_organization_and_a_square_can_follow(api: Flask) -> None:
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-3:new@example.com"}
    assert c.get(f"{PREFIX}/auth/me", headers=h).json["organizations"] == []
    r = c.post(f"{PREFIX}/organizations", json={"name": "  Bengali Club  "}, headers=h)
    assert r.status_code == 201 and [(o["name"], o["role"]) for o in r.json["organizations"]] == [("Bengali Club", "owner")]
    again = c.post(f"{PREFIX}/organizations", json={"name": "bengali club"}, headers=h)  # a double click changes nothing
    assert again.status_code == 200 and len(again.json["organizations"]) == 1
    other = c.post(f"{PREFIX}/organizations", json={"name": "Language School"}, headers=h)
    assert other.status_code == 201 and len(other.json["organizations"]) == 2


def test_organization_needs_sign_in_the_csrf_header_and_a_name(api: Flask) -> None:
    c = api.test_client()
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=HEADERS).status_code == 401
    bearer = {"Authorization": "Bearer fake:u-4:x@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=bearer).status_code == 403
    assert c.post(f"{PREFIX}/organizations", json={"name": "A"}, headers={**HEADERS, **bearer}).status_code == 422


# ---- database url handling ---------------------------------------------------------------------------------------------------------
def test_plain_postgresql_urls_get_the_psycopg_driver() -> None:
    assert make_settings(DATABASE_URL="postgresql://u:p@h:6543/postgres").DATABASE_URL == "postgresql+psycopg://u:p@h:6543/postgres"
    assert make_settings(DATABASE_URL="postgresql+psycopg://u:p@h/db").DATABASE_URL == "postgresql+psycopg://u:p@h/db"


def test_supabase_pooler_turns_prepared_statements_off() -> None:
    from app.shared.db import engine_options

    pooled = engine_options("postgresql+psycopg://u:p@aws-0-eu-west-1.pooler.supabase.com:6543/postgres")
    assert pooled["connect_args"] == {"prepare_threshold": None} and pooled["pool_pre_ping"] is True
    assert "connect_args" not in engine_options("postgresql+psycopg://u:p@127.0.0.1:5432/rootsquares_platform")


# ---- retry of a failed square -----------------------------------------------------------------------------------------------------
class RecordingExecutor:
    def __init__(self) -> None:
        self.jobs: list[tuple[Any, ...]] = []

    def submit(self, fn: Any, *args: Any) -> None:
        self.jobs.append(args)


def _square_for(api: Flask, token: str, status: str) -> tuple[str, dict[str, str]]:
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    c = api.test_client()
    org = c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=headers).json["organizations"][0]["id"]
    from app.platform.models import Square, SquareStatus

    factory = api.extensions["db_factory"]()
    with factory() as db:
        sq = Square(org_id=uuid.UUID(org), name="First", slug=f"sq-{uuid.uuid4().hex[:8]}", theme_id="paper-brick", status=SquareStatus(status), error="X")
        db.add(sq)
        db.commit()
        return str(sq.id), headers


def test_a_failed_square_can_be_tried_again_once(api: Flask) -> None:
    api.extensions["executor"] = jobs = RecordingExecutor()
    sq_id, headers = _square_for(api, "fake:u-r1:r1@example.com", "failed")
    c = api.test_client()
    r = c.post(f"{PREFIX}/squares/{sq_id}/retry", headers=headers)
    assert r.status_code == 202 and r.json["status"] == "provisioning" and r.json["error"] is None
    assert len(jobs.jobs) == 1 and jobs.jobs[0][3].email == "r1@example.com"
    again = c.post(f"{PREFIX}/squares/{sq_id}/retry", headers=headers)  # already provisioning: a double click starts nothing
    assert again.status_code == 409 and again.json["code"] == "not_failed" and len(jobs.jobs) == 1


def test_only_failed_squares_of_your_own_organisation_can_be_retried(api: Flask) -> None:
    api.extensions["executor"] = jobs = RecordingExecutor()
    ready_id, headers = _square_for(api, "fake:u-r2:r2@example.com", "ready")
    c = api.test_client()
    assert c.post(f"{PREFIX}/squares/{ready_id}/retry", headers=headers).status_code == 409
    failed_id, _ = _square_for(api, "fake:u-r3:r3@example.com", "failed")
    stranger = {**HEADERS, "Authorization": "Bearer fake:u-r4:r4@example.com"}
    assert c.post(f"{PREFIX}/squares/{failed_id}/retry", headers=stranger).status_code == 404
    assert c.post(f"{PREFIX}/squares/{uuid.uuid4()}/retry", headers=stranger).status_code == 404
    assert jobs.jobs == []


# ---- Google sign-in switch for squares (manual step by a platform admin) ----------------------------------------------------------
def test_google_login_is_requested_until_a_platform_admin_enables_it(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()
    sq_id, owner_headers = _square_for(api, "fake:u-g1:g1@example.com", "ready")
    c = api.test_client()
    shown = c.get(f"{PREFIX}/squares/{sq_id}", headers=owner_headers).json
    assert shown["google_login"] == "requested" and shown["auth_callback_url"] is None

    assert c.post(f"{PREFIX}/owner/squares/{sq_id}/google", json={"enabled": True}, headers=owner_headers).status_code == 404  # not a platform admin

    c = as_admin(api, c)
    r = c.post(f"{PREFIX}/owner/squares/{sq_id}/google", json={"enabled": True}, headers=owner_headers)
    assert r.status_code == 200 and r.json["google_login"] == "enabled"
    back = c.post(f"{PREFIX}/owner/squares/{sq_id}/google", json={"enabled": False}, headers=owner_headers)
    assert back.json["google_login"] == "requested"
    assert c.post(f"{PREFIX}/owner/squares/{uuid.uuid4()}/google", json={"enabled": True}, headers=owner_headers).status_code == 404


# ---- revocable sessions of the platform's own login (auth item F) --------------------------------------------------------------------
SIGNUP = {"email": "owner@example.com", "password": "correct-horse-1", "name": "Owner", "organization_name": "Club"}
AUTH_PATH = "/api/platform/v1/auth"


def _cookies(client: Any) -> tuple[str, str]:
    access = client.get_cookie("rs_access")
    refresh = client.get_cookie("rs_refresh", path=AUTH_PATH)
    assert access is not None and refresh is not None
    return access.value, refresh.value


def _replay(app: Flask, access: str | None = None, refresh: str | None = None) -> Any:
    """A second browser that presents copied cookies."""
    c = app.test_client()
    if access:
        c.set_cookie("rs_access", access)
    if refresh:
        c.set_cookie("rs_refresh", refresh, path=AUTH_PATH)
    return c


def test_logout_ends_the_login_on_the_server(api: Flask) -> None:
    c = api.test_client()
    assert c.post(f"{PREFIX}/auth/signup", json=SIGNUP, headers=HEADERS).status_code == 201
    access, refresh = _cookies(c)
    assert _replay(api, access).get(f"{PREFIX}/auth/me").status_code == 200  # a copy of the cookie works while the login is active
    assert c.post(f"{PREFIX}/auth/logout", headers=HEADERS).status_code == 200
    assert _replay(api, access).get(f"{PREFIX}/auth/me").status_code == 401  # ... and not after logout, although the token has not expired
    assert _replay(api, refresh=refresh).post(f"{PREFIX}/auth/refresh", headers=HEADERS).status_code == 401


def test_refresh_replaces_the_refresh_token_and_a_replay_ends_the_login(api: Flask) -> None:
    c = api.test_client()
    c.post(f"{PREFIX}/auth/signup", json=SIGNUP, headers=HEADERS)
    access0, refresh0 = _cookies(c)
    assert c.post(f"{PREFIX}/auth/refresh", headers=HEADERS).status_code == 200
    access1, refresh1 = _cookies(c)
    assert refresh1 != refresh0
    thief = _replay(api, refresh=refresh0)  # the old refresh token comes back
    assert thief.post(f"{PREFIX}/auth/refresh", headers=HEADERS).status_code == 401
    assert _replay(api, access1).get(f"{PREFIX}/auth/me").status_code == 401  # the whole login was ended, including the honest user's tokens
    assert c.post(f"{PREFIX}/auth/refresh", headers=HEADERS).status_code == 401
    assert access0 and access1


def test_two_devices_are_two_sessions_and_logout_all_ends_both(api: Flask) -> None:
    phone, laptop = api.test_client(), api.test_client()
    phone.post(f"{PREFIX}/auth/signup", json=SIGNUP, headers=HEADERS)
    assert laptop.post(f"{PREFIX}/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}, headers=HEADERS).status_code == 200
    assert phone.get(f"{PREFIX}/auth/me").status_code == 200 and laptop.get(f"{PREFIX}/auth/me").status_code == 200

    assert laptop.post(f"{PREFIX}/auth/logout", headers=HEADERS).status_code == 200
    assert phone.get(f"{PREFIX}/auth/me").status_code == 200  # logging out here does not end the other device

    laptop.post(f"{PREFIX}/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}, headers=HEADERS)
    assert laptop.post(f"{PREFIX}/auth/logout-all", headers=HEADERS).status_code == 200
    assert phone.get(f"{PREFIX}/auth/me").status_code == 401 and laptop.get(f"{PREFIX}/auth/me").status_code == 401


def test_tokens_without_a_session_id_are_refused(api: Flask) -> None:
    c = api.test_client()
    c.post(f"{PREFIX}/auth/signup", json=SIGNUP, headers=HEADERS)
    user_id = c.get(f"{PREFIX}/auth/me").json["id"]
    from app.shared.crypto import make_token

    secret = api.extensions["settings"].jwt_secret
    old_style = make_token(secret, user_id, "access", dt.timedelta(minutes=5))  # what the server issued before sessions existed
    assert _replay(api, old_style).get(f"{PREFIX}/auth/me").status_code == 401
    forged = make_token(secret, user_id, "access", dt.timedelta(minutes=5), sid=str(uuid.uuid4()))  # a session id that does not exist
    assert _replay(api, forged).get(f"{PREFIX}/auth/me").status_code == 401


def test_owner_overview_counts_and_flags_what_needs_attention(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()
    _, headers = _square_for(api, "fake:u-ov:ov@example.com", "failed")
    c = api.test_client()
    assert c.get(f"{PREFIX}/owner/overview", headers=headers).status_code == 404
    c = as_admin(api, c)
    r = c.get(f"{PREFIX}/owner/overview", headers=headers)
    assert r.status_code == 200
    assert r.json["squares_total"] == 1 and r.json["squares_failed"] == 1 and r.json["users_total"] >= 1
    assert len(r.json["weeks"]) == 8 and r.json["weeks"][-1]["users"] >= 1 and r.json["weeks"][-1]["squares"] == 1
    assert [a["kind"] for a in r.json["attention"]] == ["failed"]


def test_owner_square_actions(api: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.platform.routes as routes

    api.extensions["executor"] = RecordingExecutor()
    sq_id, headers = _square_for(api, "fake:u-oa:oa@example.com", "ready")
    c = api.test_client()
    for method, path in (("get", ""), ("post", "/suspend"), ("post", "/sync-auth"), ("post", "/check")):
        assert getattr(c, method)(f"{PREFIX}/owner/squares/{sq_id}{path}", json={"suspended": True}, headers=headers).status_code == 404
    c = as_admin(api, c)
    detail = c.get(f"{PREFIX}/owner/squares/{sq_id}", headers=headers).json
    assert detail["owner_email"] == "oa@example.com" and detail["suspended_at"] is None and "db_connection" not in detail
    assert "billing_country" in detail  # the organisation's country, for the owner console overview (W13-R18)
    assert c.get(f"{PREFIX}/owner/squares/{uuid.uuid4()}", headers=headers).status_code == 404

    slug = detail["slug"]
    assert c.get(f"{PREFIX}/public/squares/{slug}").status_code == 200
    assert c.post(f"{PREFIX}/owner/squares/{sq_id}/suspend", json={"suspended": True}, headers=headers).status_code == 200
    assert c.get(f"{PREFIX}/public/squares/{slug}").status_code == 404
    assert c.get(f"{PREFIX}/owner/squares/{sq_id}", headers=headers).json["suspended_at"] is not None
    c.post(f"{PREFIX}/owner/squares/{sq_id}/suspend", json={"suspended": False}, headers=headers)
    assert c.get(f"{PREFIX}/public/squares/{slug}").status_code == 200
    actions = [t["action"] for t in c.get(f"{PREFIX}/owner/squares/{sq_id}", headers=headers).json["timeline"]]
    assert "square.suspended" in actions and "square.unsuspended" in actions

    monkeypatch.setattr(routes, "square_database_check", lambda settings, sq: {"ok": True, "admins": 2})
    assert c.post(f"{PREFIX}/owner/squares/{sq_id}/check", headers=headers).json == {"ok": True, "admins": 2}
    # no provider token in the test settings: applying to the provider is refused, the label alone still works
    assert c.post(f"{PREFIX}/owner/squares/{sq_id}/sync-auth", headers=headers).json["code"] == "provider_unavailable"
    assert c.post(f"{PREFIX}/owner/squares/{sq_id}/google", json={"enabled": True, "apply": True}, headers=headers).json["code"] == "provider_unavailable"


def test_owner_people_and_organisations(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()
    _, admin_h = _square_for(api, "fake:u-pp1:pp1@example.com", "ready")
    _, other_h = _square_for(api, "fake:u-pp2:pp2@example.com", "ready")
    c = api.test_client()
    assert c.get(f"{PREFIX}/owner/users", headers=admin_h).status_code == 404
    assert c.get(f"{PREFIX}/owner/organizations", headers=admin_h).status_code == 404
    c = as_admin(api, c)
    users = {u["email"]: u for u in c.get(f"{PREFIX}/owner/users", headers=admin_h).json["items"]}
    assert users["pp2@example.com"]["organizations"] == 1 and "is_platform_admin" not in users["pp2@example.com"]
    assert "password_hash" not in users["pp2@example.com"]
    other_id = users["pp2@example.com"]["id"]
    detail = c.get(f"{PREFIX}/owner/users/{other_id}", headers=admin_h).json
    assert detail["orgs"][0]["role"] == "owner" and len(detail["orgs"][0]["squares"]) == 1
    assert c.get(f"{PREFIX}/owner/users/{uuid.uuid4()}", headers=admin_h).status_code == 404

    assert c.post(f"{PREFIX}/owner/users/{other_id}/logout-all", headers=admin_h).json == {"revoked": 0}  # provider users have no cookie sessions

    orgs = c.get(f"{PREFIX}/owner/organizations", headers=admin_h).json["items"]
    assert {o["owner_email"] for o in orgs} >= {"pp1@example.com", "pp2@example.com"} and all(len(o["squares"]) == 1 for o in orgs)


def test_owner_audit_log_filters_and_pages(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()
    sq_id, headers = _square_for(api, "fake:u-au:au@example.com", "ready")
    c = api.test_client()
    assert c.get(f"{PREFIX}/owner/audit", headers=headers).status_code == 404
    c = as_admin(api, c)
    c.post(f"{PREFIX}/owner/squares/{sq_id}/suspend", json={"suspended": True}, headers=headers)
    c.post(f"{PREFIX}/owner/squares/{sq_id}/suspend", json={"suspended": False}, headers=headers)

    everything = c.get(f"{PREFIX}/owner/audit", headers=headers).json
    assert {"square.suspended", "square.unsuspended"} <= {i["action"] for i in everything["items"]}
    assert any(i["actor_email"] == "au@example.com" for i in everything["items"])
    only_square = c.get(f"{PREFIX}/owner/audit?action_prefix=square.", headers=headers).json["items"]
    assert only_square and all(i["action"].startswith("square.") for i in only_square)
    assert c.get(f"{PREFIX}/owner/audit?action_prefix=%25", headers=headers).json["items"] == []  # a wildcard is taken literally
    by_square = c.get(f"{PREFIX}/owner/audit?square_id={sq_id}", headers=headers).json["items"]
    assert {i["action"] for i in by_square} >= {"square.suspended", "square.unsuspended"} and all(i["entity_id"] == sq_id for i in by_square)
    # paging: rows with explicit timestamps, two of them identical (rows of one request share a timestamp)
    stamp = dt.datetime(2030, 1, 1, 12, 0, 0, 123456, tzinfo=dt.UTC)
    with api.extensions["db_factory"]()() as db:
        for at in (stamp, stamp, stamp + dt.timedelta(seconds=1)):
            db.add(AuditLog(at=at, action="test.page", entity="x", entity_id="1", data={}))
        db.commit()
    first = c.get(f"{PREFIX}/owner/audit", query_string={"limit": 1, "action_prefix": "test."}, headers=headers).json
    assert len(first["items"]) == 1 and first["next_before"]
    seen = [first["items"][0]["id"]]
    cursor = first["next_before"]
    while cursor:  # walks the log one row at a time without repeating or skipping
        page = c.get(f"{PREFIX}/owner/audit", query_string={"limit": 1, "before": cursor, "action_prefix": "test."}, headers=headers).json
        seen.append(page["items"][0]["id"])
        cursor = page["next_before"]
    assert len(seen) == 3 and len(set(seen)) == 3
    assert c.get(f"{PREFIX}/owner/audit?square_id=nope", headers=headers).json["code"] == "bad_filter"


def test_owner_health_reports_checks_and_never_a_secret(tmp_path: Path) -> None:
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.supabase.com":
            ok = request.headers.get("authorization") == "Bearer SECRET-TOKEN-XYZ"
            return httpx.Response(200 if ok else 401, json=[{"slug": "my-org"}])
        return httpx.Response(200, json={"keys": []})  # the platform auth project's key set

    settings = make_settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'platform.db'}",
        PROVISIONER="supabase",
        SUPABASE_ACCESS_TOKEN="SECRET-TOKEN-XYZ",
        SUPABASE_ORG_SLUG="my-org",
        AUTH_PROVIDER="supabase",
        AUTH_URL="https://abc.supabase.co",
        GOOGLE_OAUTH_CLIENT_ID="cid",
        GOOGLE_OAUTH_CLIENT_SECRET="SECRET-GOOGLE",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.extensions["db_engine"]())
    app.extensions["providers"].auth = FakeAuthProvider()
    app.extensions["health_http_client"] = httpx.Client(transport=httpx.MockTransport(handler))
    _, headers = _square_for(app, "fake:u-h:h@example.com", "ready")
    c = app.test_client()
    assert c.get(f"{PREFIX}/owner/health", headers=headers).status_code == 404
    c = as_admin(app, c)
    r = c.get(f"{PREFIX}/owner/health", headers=headers)
    assert r.status_code == 200
    by_id = {x["id"]: x for x in r.json["checks"]}
    assert by_id["database"]["status"] == "ok" and by_id["platform_auth"]["status"] == "ok"
    assert by_id["provider_token"] == {"id": "provider_token", "status": "ok", "detail": "token works"}
    assert by_id["storage"]["status"] == "warn" and by_id["google_client"]["status"] == "ok" and by_id["jwt_secret"]["status"] == "warn"
    assert r.json["environment"]["auth_host"] == "abc.supabase.co" and r.json["environment"]["provisioner"] == "supabase"
    assert "SECRET" not in r.get_data(as_text=True)
