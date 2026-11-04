"""Tests for auth providers (7 tests), e.g. get auth provider returns supabase by default; get auth provider returns neon when configured; get auth provider raises on an unrecognized value."""
from unittest.mock import patch

import jwt
import pytest

from app import create_app
from app.auth.providers import NeonAuthProvider, SupabaseAuthProvider, get_auth_provider
from tests.auth_helpers import FakeJWKClient, FakeNeonJWKClient, make_neon_token, make_token


def test_get_auth_provider_returns_supabase_by_default():
    app = create_app("testing")
    with app.app_context():
        assert isinstance(get_auth_provider(), SupabaseAuthProvider)
        assert get_auth_provider().name == "supabase"


def test_get_auth_provider_returns_neon_when_configured():
    app = create_app("testing")
    app.config["AUTH_PROVIDER"] = "neon"
    with app.app_context():
        assert isinstance(get_auth_provider(), NeonAuthProvider)
        assert get_auth_provider().name == "neon"


def test_get_auth_provider_raises_on_an_unrecognized_value():
    app = create_app("testing")
    app.config["AUTH_PROVIDER"] = "something-else"
    with app.app_context():
        with pytest.raises(ValueError):
            get_auth_provider()


def test_supabase_provider_verify_returns_normalized_claims():
    app = create_app("testing")
    app.config["AUTH_URL"] = "https://example.supabase.co"
    with app.app_context():
        token = make_token(sub="user-1", email="a@b.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            claims = SupabaseAuthProvider().verify(token)
        assert claims == {"sub": "user-1", "email": "a@b.com"}


def test_neon_provider_verify_returns_normalized_claims():
    app = create_app("testing")
    app.config["AUTH_URL"] = "https://example-neon-auth.tech"
    with app.app_context():
        token = make_neon_token(sub="user-2", email="c@d.com", issuer="https://example-neon-auth.tech")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
            claims = NeonAuthProvider().verify(token)
        assert claims == {"sub": "user-2", "email": "c@d.com"}


def test_supabase_token_rejected_when_neon_provider_is_active():
    app = create_app("testing")
    app.config["AUTH_URL"] = "https://example-neon-auth.tech"
    with app.app_context():
        # ES256-signed Supabase token presented to the EdDSA-only Neon verifier.
        token = make_token(sub="user-1", email="a@b.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
            with pytest.raises(jwt.PyJWTError):
                NeonAuthProvider().verify(token)


def test_neon_token_rejected_when_supabase_provider_is_active():
    app = create_app("testing")
    app.config["AUTH_URL"] = "https://example.supabase.co"
    with app.app_context():
        # EdDSA-signed Neon token presented to the ES256-only Supabase verifier.
        token = make_neon_token(sub="user-2", email="c@d.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            with pytest.raises(jwt.PyJWTError):
                SupabaseAuthProvider().verify(token)
