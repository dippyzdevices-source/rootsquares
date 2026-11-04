"""Tests for neon webhook verification (13 tests), e.g. accepts a correctly signed fresh request; accepts a body with non ascii text and odd whitespace; rejects a tampered body."""
import json
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.auth.webhook_verification import (
    NeonWebhookError,
    NeonWebhookKeyUnavailable,
    verify_neon_webhook,
)
from tests.auth_helpers import FakeSigningKey, _public_key as _ec_public_key
from tests.neon_webhook_helpers import (
    NEON_AUTH_URL,
    FakeWebhookJWKClient,
    UnreachableJWKClient,
    sign_webhook,
)

BODY = json.dumps({"event_type": "send.otp"}).encode("utf-8")
PATCH_TARGET = "app.auth.jwt_verification._get_jwks_client"


def _verify(body=BODY, headers=None, client=None):
    with patch(PATCH_TARGET, return_value=client or FakeWebhookJWKClient()):
        verify_neon_webhook(body, headers if headers is not None else sign_webhook(body), NEON_AUTH_URL)


def test_accepts_a_correctly_signed_fresh_request():
    _verify()  # no exception


def test_accepts_a_body_with_non_ascii_text_and_odd_whitespace():
    # Review Focus #1: the signature is over the exact raw bytes, never a re-serialized JSON.
    body = '{ "user":  {"name": "Sørensen — বাংলা"} ,\n "event_type":"send.otp" }'.encode("utf-8")
    _verify(body=body)


def test_rejects_a_tampered_body():
    headers = sign_webhook(BODY)
    with pytest.raises(NeonWebhookError):
        _verify(body=BODY + b" ", headers=headers)


def test_rejects_a_signature_from_a_different_key():
    wrong_key = ed25519.Ed25519PrivateKey.generate()
    with pytest.raises(NeonWebhookError):
        _verify(headers=sign_webhook(BODY, key=wrong_key))


@pytest.mark.parametrize("missing", ["X-Neon-Signature", "X-Neon-Signature-Kid", "X-Neon-Timestamp"])
def test_rejects_a_request_missing_a_required_header(missing):
    headers = sign_webhook(BODY)
    del headers[missing]
    with pytest.raises(NeonWebhookError):
        _verify(headers=headers)


def test_rejects_a_stale_timestamp():
    stale = int(time.time() * 1000) - 6 * 60 * 1000
    with pytest.raises(NeonWebhookError):
        _verify(headers=sign_webhook(BODY, timestamp_ms=stale))


def test_rejects_a_timestamp_too_far_in_the_future():
    future = int(time.time() * 1000) + 6 * 60 * 1000
    with pytest.raises(NeonWebhookError):
        _verify(headers=sign_webhook(BODY, timestamp_ms=future))


def test_accepts_a_timestamp_just_inside_the_window():
    _verify(headers=sign_webhook(BODY, timestamp_ms=int(time.time() * 1000) - 4 * 60 * 1000))


def test_rejects_a_non_numeric_timestamp():
    headers = sign_webhook(BODY)
    headers["X-Neon-Timestamp"] = "not-a-number"
    with pytest.raises(NeonWebhookError):
        _verify(headers=headers)


@pytest.mark.parametrize("signature", ["abc", "a.b.c", "a.b", ".."])
def test_rejects_a_signature_that_is_not_a_detached_jws(signature):
    headers = sign_webhook(BODY)
    headers["X-Neon-Signature"] = signature
    with pytest.raises(NeonWebhookError):
        _verify(headers=headers)


def test_rejects_an_unknown_key_id():
    with pytest.raises(NeonWebhookError):
        _verify(headers=sign_webhook(BODY, kid="some-other-kid"))


def test_rejects_a_signing_key_that_is_not_ed25519():
    class EcClient:
        def get_signing_key(self, kid):
            return FakeSigningKey(_ec_public_key)

    with pytest.raises(NeonWebhookError):
        _verify(client=EcClient())


def test_reports_unreachable_jwks_as_key_unavailable_not_an_invalid_request():
    # Review Focus #3: a Neon-side outage must be retryable, never a permanent 401.
    with pytest.raises(NeonWebhookKeyUnavailable):
        _verify(client=UnreachableJWKClient())
