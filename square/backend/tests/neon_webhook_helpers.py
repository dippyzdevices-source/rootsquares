"""Helpers for testing Neon Auth webhooks: a throwaway Ed25519 signing key, fake JWKS clients,
and sign_webhook(), which signs a body exactly the way Neon documents
(https://neon.com/docs/auth/guides/webhooks): a detached JWS whose signing input is
`header.b64url(timestamp.b64url(raw_body))`.
"""

import base64
import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519

from tests.auth_helpers import FakeSigningKey

KID = "test-kid"
NEON_AUTH_URL = "https://ep-test.aws.neon.tech/neondb/auth"

_private_key = ed25519.Ed25519PrivateKey.generate()
_public_key = _private_key.public_key()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class FakeWebhookJWKClient:
    """Stands in for PyJWKClient: knows exactly one key id, and raises like PyJWKClient for any other."""

    def get_signing_key(self, kid):
        if kid != KID:
            raise jwt.PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
        return FakeSigningKey(_public_key)


class UnreachableJWKClient:
    def get_signing_key(self, kid):
        raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")


def sign_webhook(
    raw_body: bytes, *, timestamp_ms: int | None = None, kid: str = KID, key=None
) -> dict[str, str]:
    """Headers Neon would send for raw_body. Pass `key` to sign with the wrong private key."""
    timestamp = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    header_b64 = _b64url(json.dumps({"alg": "EdDSA", "kid": kid}).encode("utf-8"))
    payload_b64 = _b64url(raw_body)
    signed_payload_b64 = _b64url(f"{timestamp}.{payload_b64}".encode("utf-8"))
    signing_input = f"{header_b64}.{signed_payload_b64}".encode("ascii")
    signature = (key or _private_key).sign(signing_input)
    return {
        "X-Neon-Signature": f"{header_b64}..{_b64url(signature)}",
        "X-Neon-Signature-Kid": kid,
        "X-Neon-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


def otp_payload(
    *,
    code: str = "123456",
    otp_type: str = "email-verification",
    email: str = "priya@example.com",
    event_id: str = "evt-otp-1",
    expires_at: str | None = "2099-01-01T00:00:00Z",
    delivery_preference: str | None = None,
) -> dict:
    event_data = {"otp_code": code, "otp_type": otp_type, "expires_at": expires_at}
    if delivery_preference:
        event_data["delivery_preference"] = delivery_preference
    return {
        "event_id": event_id,
        "event_type": "send.otp",
        "timestamp": "2026-09-24T12:00:00Z",
        "user": {"id": "user-1", "email": email},
        "event_data": event_data,
    }


def magic_link_payload(
    *,
    link_url: str = "https://ep-test.aws.neon.tech/neondb/auth/reset-password/tok123?callbackURL=http://localhost:5173/reset-password",
    link_type: str = "forget-password",
    email: str = "priya@example.com",
    event_id: str = "evt-link-1",
    expires_at: str | None = "2099-01-01T00:00:00Z",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": "send.magic_link",
        "timestamp": "2026-09-24T12:00:00Z",
        "user": {"id": "user-1", "email": email},
        "event_data": {
            "link_type": link_type,
            "link_url": link_url,
            "token": "tok123",
            "expires_at": expires_at,
        },
    }
