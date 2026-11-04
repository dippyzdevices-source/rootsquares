"""Tests for auth service (3 tests), e.g. resolve user from token jit provisions a new user; resolve user from token reuses the existing user and never duplicates; resolve user from token returns none for an invalid token."""
from unittest.mock import patch

from app import create_app
from app.auth.models import User
from app.auth.service import resolve_user_from_token
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, make_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_resolve_user_from_token_jit_provisions_a_new_user():
    app = _new_app()
    with app.app_context():
        token = make_token(sub="brand-new-sub", email="new@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            user = resolve_user_from_token(token)

        assert user is not None
        assert user.email == "new@example.com"
        assert user.auth_user_id == "brand-new-sub"
        assert user.auth_provider == "supabase"
        db.drop_all()


def test_resolve_user_from_token_reuses_the_existing_user_and_never_duplicates():
    app = _new_app()
    with app.app_context():
        token = make_token(sub="existing-sub", email="existing@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            first = resolve_user_from_token(token)
            second = resolve_user_from_token(token)

        assert first.id == second.id
        assert User.query.filter_by(auth_user_id="existing-sub").count() == 1
        db.drop_all()


def test_resolve_user_from_token_returns_none_for_an_invalid_token():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            user = resolve_user_from_token("not-a-real-token")
        assert user is None
        db.drop_all()
