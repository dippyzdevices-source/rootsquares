"""Verification of Neon Auth (Managed Better Auth) webhook signatures.

Neon signs every webhook with EdDSA (Ed25519) as a *detached* JWS: `X-Neon-Signature` is
`<header>..<signature>` with an empty payload part. The signed bytes are
`<header>.<b64url(timestamp + "." + b64url(raw_body))>` — base64url applied twice — so the
signature covers both the exact raw request bytes and `X-Neon-Timestamp`. Reference:
https://neon.com/docs/auth/guides/webhooks
"""

import base64
import binascii
import time

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.auth import jwt_verification

MAX_TIMESTAMP_SKEW_MS = 5 * 60 * 1000


class NeonWebhookError(Exception):
    """Not a valid, fresh, correctly signed Neon webhook — the route answers 401."""


class NeonWebhookKeyUnavailable(Exception):
    """Neon's signing keys (JWKS) couldn't be fetched right now. Not the caller's fault, so the
    route answers 503 and Neon retries, instead of a 401 that would fail the user's sign-up."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def verify_neon_webhook(raw_body: bytes, headers, neon_auth_url: str) -> None:
    signature = headers.get("X-Neon-Signature")
    kid = headers.get("X-Neon-Signature-Kid")
    timestamp = headers.get("X-Neon-Timestamp")
    if not signature or not kid or not timestamp:
        raise NeonWebhookError("Missing required Neon webhook headers")
    try:
        timestamp_ms = int(timestamp)
    except ValueError:
        raise NeonWebhookError("Malformed X-Neon-Timestamp") from None

    parts = signature.split(".")
    if len(parts) != 3 or parts[1] != "":
        raise NeonWebhookError("Expected a detached JWS signature")
    header_b64, _, signature_b64 = parts
    try:
        signature_bytes = _b64url_decode(signature_b64)
    except (binascii.Error, ValueError):
        raise NeonWebhookError("Malformed signature") from None

    # Called through the module (not `from ... import`) so tests can patch
    # app.auth.jwt_verification._get_jwks_client, the same way the token tests do.
    client = jwt_verification._get_jwks_client(f"{neon_auth_url}/.well-known/jwks.json")
    try:
        signing_key = client.get_signing_key(kid)
    except jwt.PyJWKClientConnectionError as exc:
        raise NeonWebhookKeyUnavailable(str(exc)) from exc
    except jwt.PyJWTError as exc:
        raise NeonWebhookError("Unknown signing key") from exc
    if not isinstance(signing_key.key, Ed25519PublicKey):
        raise NeonWebhookError("Unsupported signing key type")

    signed_payload_b64 = _b64url_encode(f"{timestamp}.{_b64url_encode(raw_body)}".encode("utf-8"))
    try:
        signing_input = f"{header_b64}.{signed_payload_b64}".encode("ascii")
    except UnicodeEncodeError:
        raise NeonWebhookError("Malformed signature header") from None
    try:
        signing_key.key.verify(signature_bytes, signing_input)
    except InvalidSignature:
        raise NeonWebhookError("Invalid webhook signature") from None

    if abs(int(time.time() * 1000) - timestamp_ms) > MAX_TIMESTAMP_SKEW_MS:
        raise NeonWebhookError("Webhook timestamp outside the allowed window")
