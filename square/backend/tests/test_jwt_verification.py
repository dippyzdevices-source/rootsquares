"""Tests for jwt verification (9 tests), e.g. verify supabase token returns claims for a valid token; verify supabase token rejects an expired token; verify supabase token rejects a bad signature."""
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.jwt_verification import verify_supabase_token
from tests.auth_helpers import FakeJWKClient, make_token


def test_verify_supabase_token_returns_claims_for_a_valid_token():
    token = make_token(sub="user-123", email="a@b.com")

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        claims = verify_supabase_token(token, "https://example.supabase.co")

    assert claims["sub"] == "user-123"
    assert claims["email"] == "a@b.com"


def test_verify_supabase_token_rejects_an_expired_token():
    token = make_token(exp_delta=-10)

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_supabase_token(token, "https://example.supabase.co")


def test_verify_supabase_token_rejects_a_bad_signature():
    wrong_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 3600},
        wrong_key,
        algorithm="ES256",
    )

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_supabase_token(token, "https://example.supabase.co")


def test_verify_supabase_token_rejects_wrong_audience():
    token = make_token(aud="something-else")

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_supabase_token(token, "https://example.supabase.co")


from app.auth.jwt_verification import verify_neon_token
from tests.auth_helpers import FakeNeonJWKClient, make_neon_token


def test_verify_neon_token_returns_claims_for_a_valid_token():
    token = make_neon_token(sub="neon-user-123", email="a@b.com")

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
        claims = verify_neon_token(token, "https://example-neon-auth.tech")

    assert claims["sub"] == "neon-user-123"
    assert claims["email"] == "a@b.com"


def test_verify_neon_token_rejects_an_expired_token():
    token = make_neon_token(exp_delta=-10)

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_neon_token(token, "https://example-neon-auth.tech")


def test_verify_neon_token_rejects_a_bad_signature():
    from cryptography.hazmat.primitives.asymmetric import ed25519

    wrong_key = ed25519.Ed25519PrivateKey.generate()
    token = jwt.encode(
        {"sub": "x", "iss": "https://example-neon-auth.tech", "exp": int(time.time()) + 900},
        wrong_key,
        algorithm="EdDSA",
    )

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_neon_token(token, "https://example-neon-auth.tech")


def test_verify_neon_token_rejects_a_mismatched_issuer():
    # Neon Auth URL configured is a different origin than the token was actually issued for.
    token = make_neon_token(issuer="https://attacker-controlled.tech")

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_neon_token(token, "https://example-neon-auth.tech")


def test_verify_neon_token_rejects_a_mismatched_audience():
    token = make_neon_token(aud="https://some-other-audience.tech")

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeNeonJWKClient()):
        with pytest.raises(jwt.PyJWTError):
            verify_neon_token(token, "https://example-neon-auth.tech")
