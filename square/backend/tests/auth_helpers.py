"""Test helper (auth helpers) used by the tests in this folder."""
import time
import uuid

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from app.auth.models import User
from app.extensions import db

_private_key = ec.generate_private_key(ec.SECP256R1())
_public_key = _private_key.public_key()

_neon_private_key = ed25519.Ed25519PrivateKey.generate()
_neon_public_key = _neon_private_key.public_key()


def make_token(sub: str | None = None, email: str = "test@example.com", exp_delta: int = 3600, **extra_claims) -> str:
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "email": email,
        "aud": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",  # the issuer of TestingConfig.AUTH_URL; pass iss=... to test another project
        "exp": int(time.time()) + exp_delta,
        **extra_claims,
    }
    return jwt.encode(payload, _private_key, algorithm="ES256")


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJWKClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey(_public_key)


def make_neon_token(
    sub: str | None = None,
    email: str = "test@example.com",
    exp_delta: int = 900,
    issuer: str = "https://example-neon-auth.tech",
    aud: str | None = None,
    **extra_claims,
) -> str:
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "email": email,
        "iss": issuer,
        "aud": aud or issuer,
        "exp": int(time.time()) + exp_delta,
        **extra_claims,
    }
    return jwt.encode(payload, _neon_private_key, algorithm="EdDSA")


class FakeNeonJWKClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey(_neon_public_key)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_user_and_token(role: str = "member", email: str = "test@example.com") -> tuple[User, str]:
    """Create a local User row with the given role and a matching valid token.

    Must be called inside an active app context with tables already created.
    """
    sub = str(uuid.uuid4())
    user = User(auth_user_id=sub, auth_provider="supabase", email=email, role=role)
    db.session.add(user)
    db.session.commit()
    token = make_token(sub=sub, email=email)
    return user, token
