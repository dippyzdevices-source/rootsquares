"""Tests for auth decorators (6 tests), e.g. require auth rejects missing authorization header; require auth rejects invalid token; require auth jit provisions a new user."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_token, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_require_auth_rejects_missing_authorization_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/auth/me")
        assert response.status_code == 401
        db.drop_all()


def test_require_auth_rejects_invalid_token():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/auth/me", headers=auth_header("not-a-real-token")
            )
        assert response.status_code == 401
        db.drop_all()


def test_require_auth_jit_provisions_a_new_user():
    app = _new_app()
    with app.app_context():
        token = make_token(sub="brand-new-sub", email="new@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/auth/me", headers=auth_header(token))

        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "member"

        db.drop_all()


def test_require_auth_reuses_the_existing_user_on_a_second_call():
    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(role="admin", email="existing@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/auth/me", headers=auth_header(token))

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == user.id
        assert data["role"] == "admin"

        db.drop_all()


def test_require_auth_decorated_route_allows_a_cors_preflight_with_no_auth_header():
    # Regression test: a real browser's CORS preflight OPTIONS request never carries an
    # Authorization header. Rejecting it with 401 makes the browser treat the whole
    # preflight as failed and block the real request — this bug shipped invisibly
    # because pytest's test client bypasses real CORS preflight entirely, and was only
    # caught via live browser testing.
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/auth/me", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_require_role_before_request_allows_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/events", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()
