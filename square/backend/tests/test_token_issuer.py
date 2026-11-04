"""Supabase tokens are checked for who issued them, not only who they are for (rootsquares W6-R37, hardcodings 8)."""

from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_token


def _me(token: str) -> int:
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            return app.test_client().get("/api/auth/me", headers=auth_header(token)).status_code


def test_a_token_from_the_configured_project_is_accepted():
    assert _me(make_token()) == 200  # the helper's default issuer is TestingConfig.AUTH_URL + /auth/v1


def test_a_token_from_another_project_is_refused():
    assert _me(make_token(iss="https://someone-else.supabase.co/auth/v1")) == 401


def test_a_token_without_an_issuer_is_refused():
    import time

    import jwt

    from tests.auth_helpers import _private_key

    payload = {"sub": "u1", "email": "a@b.c", "aud": "authenticated", "exp": int(time.time()) + 3600}
    assert _me(jwt.encode(payload, _private_key, algorithm="ES256")) == 401
