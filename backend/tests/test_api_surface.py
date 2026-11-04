"""One codebase, two services (ADR 084, database option B): API_SURFACE decides which routes a process serves; staff secrets are separate.

The customer service has no staff address at all, the admin service has no customer address; both answer the health checks. The staff cookie is signed
and the staff TOTP secrets are encrypted with their own keys, and production refuses a setting that would mix the two worlds again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from pydantic import ValidationError

from app.main import create_app
from app.platform import staff
from app.platform.admin_auth import STAFF_COOKIE
from app.platform.models import StaffUser
from app.shared.crypto import Encryptor, read_token
from app.shared.db import Base
from tests.conftest import make_settings
from tests.staff_client import ADMIN, staff_client

CUSTOMER_ORIGIN = "http://localhost:5273"
ADMIN_ORIGIN = "http://localhost:5275"


def _app(tmp_path: Path, surface: str, **extra: object) -> Flask:
    origins = {"CORS_ORIGINS": CUSTOMER_ORIGIN, "ADMIN_ORIGINS": ADMIN_ORIGIN}  # outside the local environment no origin is allowed by default
    app = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / f'{surface}.db'}", API_SURFACE=surface, **origins, **extra))
    Base.metadata.create_all(app.extensions["db_engine"]())
    return app


def _rules(app: Flask) -> set[str]:
    return {r.rule for r in app.url_map.iter_rules()}


def _staff_rules(app: Flask) -> set[str]:
    return {r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/api/admin/v1")}


@pytest.fixture
def customer(tmp_path: Path) -> Flask:
    return _app(tmp_path, "customer")


@pytest.fixture
def admin(tmp_path: Path) -> Flask:
    return _app(tmp_path, "admin")


@pytest.fixture
def everything(tmp_path: Path) -> Flask:
    return _app(tmp_path, "all")


# ---- which routes each surface mounts ----------------------------------------------------------------------------------------------
def test_the_customer_service_has_no_staff_address(customer: Flask) -> None:
    assert not [r for r in _rules(customer) if r.startswith("/api/admin")]
    assert "/api/platform/v1/auth/me" in _rules(customer)


def test_the_admin_service_has_no_customer_address(admin: Flask) -> None:
    assert not [r for r in _rules(admin) if r.startswith("/api/platform")]
    assert "/api/admin/v1/auth/login" in _rules(admin)


def test_both_services_have_the_health_checks(customer: Flask, admin: Flask) -> None:
    for app in (customer, admin):
        c = app.test_client()
        assert c.get("/healthz").status_code == 200
        assert c.get("/readyz").status_code == 200


def test_the_admin_service_mounts_the_same_staff_routes_as_the_single_process(admin: Flask, everything: Flask) -> None:
    assert _staff_rules(admin) == _staff_rules(everything)
    assert len(_staff_rules(admin)) > 40  # the sign-in routes and the shared handlers (a scratch app builds them without a customer route)


def test_the_single_process_serves_both(everything: Flask) -> None:
    assert any(r.startswith("/api/platform/v1") for r in _rules(everything)) and _staff_rules(everything)


def test_each_service_answers_404_for_the_other_ones_addresses(customer: Flask, admin: Flask) -> None:
    assert customer.test_client().get("/api/admin/v1/auth/me").status_code == 404
    assert customer.test_client().get("/api/admin/v1/audit").status_code == 404
    assert admin.test_client().get("/api/platform/v1/auth/me").status_code == 404
    assert admin.test_client().get("/api/platform/v1/public/squares/x").status_code == 404
    assert admin.test_client().post("/api/platform/v1/auth/login", json={}).status_code == 404


# ---- CORS follows the surface ------------------------------------------------------------------------------------------------------
def test_cors_answers_the_origins_of_the_surface_only(customer: Flask, admin: Flask) -> None:
    cust = customer.test_client().get("/api/platform/v1/auth/me", headers={"Origin": CUSTOMER_ORIGIN})
    assert cust.headers.get("Access-Control-Allow-Origin") == CUSTOMER_ORIGIN
    adm = admin.test_client().get("/api/admin/v1/auth/me", headers={"Origin": ADMIN_ORIGIN})
    assert adm.headers.get("Access-Control-Allow-Origin") == ADMIN_ORIGIN
    # the customer service has no CORS rule for the staff path, and the admin service none for the customer origin
    assert customer.test_client().get("/api/admin/v1/auth/me", headers={"Origin": ADMIN_ORIGIN}).headers.get("Access-Control-Allow-Origin") is None
    assert admin.test_client().get("/api/admin/v1/auth/me", headers={"Origin": CUSTOMER_ORIGIN}).headers.get("Access-Control-Allow-Origin") is None


# ---- separate staff secrets ---------------------------------------------------------------------------------------------------------
def _signed_in(tmp_path: Path) -> tuple[Flask, object]:
    app = _app(tmp_path, "all", STAFF_JWT_SECRET="s" * 40, STAFF_FERNET_KEY=_fernet_key(1))
    return app, staff_client(app)


def _fernet_key(seed: int) -> str:
    import base64
    import hashlib

    return base64.urlsafe_b64encode(hashlib.sha256(f"test-fernet-{seed}".encode()).digest()).decode()


def test_the_staff_cookie_is_signed_with_the_staff_secret_not_the_customer_one(tmp_path: Path) -> None:
    app, client = _signed_in(tmp_path)
    token = client.get_cookie(STAFF_COOKIE).value  # type: ignore[attr-defined]
    s = app.extensions["settings"]
    assert read_token(s.staff_jwt_secret, token, "staff") is not None
    assert read_token(s.jwt_secret, token, "staff") is None


def test_a_staff_token_made_with_the_customer_secret_is_not_a_login(tmp_path: Path) -> None:
    import datetime as dt

    from app.shared.crypto import make_token

    app, client = _signed_in(tmp_path)
    with app.extensions["db_factory"]()() as db:
        member = db.query(StaffUser).first()
        assert member is not None
        forged = make_token(app.extensions["settings"].jwt_secret, str(member.id), "staff", dt.timedelta(hours=1))
    fresh = app.test_client()
    fresh.set_cookie(STAFF_COOKIE, forged)
    assert fresh.get(f"{ADMIN}/auth/me").status_code == 401
    assert client.get(f"{ADMIN}/auth/me").status_code == 200


def test_the_totp_secret_is_encrypted_with_the_staff_key_not_the_shared_one(tmp_path: Path) -> None:
    app, _client = _signed_in(tmp_path)
    s = app.extensions["settings"]
    with app.extensions["db_factory"]()() as db:
        member = db.query(StaffUser).first()
        assert member is not None and member.totp_secret
        assert staff.totp_code(Encryptor(s.staff_fernet_key).decrypt(member.totp_secret))  # opens with the staff key
        with pytest.raises(ValueError):
            Encryptor(s.fernet_key).decrypt(member.totp_secret)  # not with the key that protects the squares


def test_outside_production_the_staff_secrets_fall_back_to_the_shared_ones() -> None:
    s = make_settings()
    assert s.staff_jwt_secret == s.jwt_secret and s.staff_fernet_key == s.fernet_key
    t = make_settings(STAFF_JWT_SECRET="s" * 40)
    assert t.staff_jwt_secret == "s" * 40 and t.staff_fernet_key == t.fernet_key


# ---- production refuses a mixed setup ------------------------------------------------------------------------------------------------
BASE = {
    "ENV": "production",
    "FERNET_KEY": "k",
    "DATABASE_URL": "postgresql+psycopg://u:p@h/db",
    "COOKIE_SECURE": True,
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
CUSTOMER_SIDE = {**BASE, "API_SURFACE": "customer", "JWT_SECRET": "j" * 40}
ADMIN_SIDE = {
    **BASE,
    "API_SURFACE": "admin",
    "ADMIN_ORIGINS": "https://admin.example.com",
    "STAFF_JWT_SECRET": "t" * 40,
    "STAFF_FERNET_KEY": "sk",
    "SUPPORT_SESSION_KEY": "u" * 40,
}


def _prod(base: dict[str, object], **changes: object) -> object:
    from app.shared.config import Settings

    return Settings(_env_file=None, **{**base, **changes})  # type: ignore[call-arg]


def test_production_runs_two_services_never_one() -> None:
    _prod(CUSTOMER_SIDE)
    _prod(ADMIN_SIDE)
    with pytest.raises(ValidationError, match="API_SURFACE must be customer or admin"):
        _prod({**CUSTOMER_SIDE, "API_SURFACE": "all"})


def test_the_customer_service_needs_its_secret_and_may_not_hold_staff_secrets() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _prod(CUSTOMER_SIDE, JWT_SECRET="")
    with pytest.raises(ValidationError, match="must not hold STAFF_JWT_SECRET"):
        _prod(CUSTOMER_SIDE, STAFF_JWT_SECRET="t" * 40)
    with pytest.raises(ValidationError, match="must not hold STAFF_JWT_SECRET"):
        _prod(CUSTOMER_SIDE, STAFF_FERNET_KEY="sk")
    with pytest.raises(ValidationError, match="must not hold STAFF_JWT_SECRET"):
        _prod(CUSTOMER_SIDE, SUPPORT_SESSION_KEY="u" * 40)  # the support signing key belongs to the admin service only (ADR 089)


def test_production_refuses_to_start_without_the_staff_second_step() -> None:
    with pytest.raises(ValidationError, match="STAFF_SECOND_STEP_REQUIRED"):
        _prod(ADMIN_SIDE, STAFF_SECOND_STEP_REQUIRED=False)
    _prod(ADMIN_SIDE, STAFF_SECOND_STEP_REQUIRED=True)


def test_the_customer_service_may_not_hold_the_render_key() -> None:
    with pytest.raises(ValidationError, match="must not hold RENDER_API_KEY"):
        _prod(CUSTOMER_SIDE, RENDER_API_KEY="rnd_key")  # the Render account key belongs to the admin service only (ADR 098)
    _prod(ADMIN_SIDE, RENDER_API_KEY="rnd_key", RENDER_SITE_SERVICE_ID="srv-abc123")


def test_the_admin_service_needs_its_own_staff_secrets_and_an_admin_origin() -> None:
    with pytest.raises(ValidationError, match="ADMIN_ORIGINS"):
        _prod(ADMIN_SIDE, ADMIN_ORIGINS="")
    with pytest.raises(ValidationError, match="STAFF_JWT_SECRET"):
        _prod(ADMIN_SIDE, STAFF_JWT_SECRET="short")
    with pytest.raises(ValidationError, match="STAFF_FERNET_KEY"):
        _prod(ADMIN_SIDE, STAFF_FERNET_KEY="")
    with pytest.raises(ValidationError, match="SUPPORT_SESSION_KEY"):
        _prod(ADMIN_SIDE, SUPPORT_SESSION_KEY="")
    with pytest.raises(ValidationError, match="SUPPORT_SESSION_KEY must differ"):
        _prod(ADMIN_SIDE, SUPPORT_SESSION_KEY="t" * 40)  # the same value as the staff secret
    with pytest.raises(ValidationError, match="must differ"):
        _prod(ADMIN_SIDE, JWT_SECRET="t" * 40)  # the same value as the staff secret
    with pytest.raises(ValidationError, match="must differ"):
        _prod(ADMIN_SIDE, FERNET_KEY="sk")
    _prod(ADMIN_SIDE, JWT_SECRET="j" * 40)  # holding a different customer secret is allowed, only sharing is not
