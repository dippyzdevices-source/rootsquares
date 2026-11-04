"""Tests for neon webhooks (20 tests), e.g. send otp email verification sends the branded code email; send magic link forget password sends the branded reset email; returns 404 and sends nothing when neon auth is not configured."""
import json
import logging
import time
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ed25519

from app import create_app
from app.email.service import EmailServiceError, EmailServiceNotConfiguredError
from tests.neon_webhook_helpers import (
    NEON_AUTH_URL,
    FakeWebhookJWKClient,
    UnreachableJWKClient,
    magic_link_payload,
    otp_payload,
    sign_webhook,
)

URL = "/api/webhooks/neon-auth"
PATCH_TARGET = "app.auth.jwt_verification._get_jwks_client"


def _app(auth_url=NEON_AUTH_URL, auth_provider="neon"):
    app = create_app("testing")
    app.config["AUTH_URL"] = auth_url
    # TestingConfig deliberately stays on "supabase"; the route is only live for "neon".
    app.config["AUTH_PROVIDER"] = auth_provider
    return app


def _post(app, payload, *, jwks=None, **sign_kwargs):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    with patch(PATCH_TARGET, return_value=jwks or FakeWebhookJWKClient()):
        return app.test_client().post(URL, data=raw, headers=sign_webhook(raw, **sign_kwargs))


def _sent(app):
    return app.extensions["email_service"].sent_emails


def test_send_otp_email_verification_sends_the_branded_code_email():
    app = _app()
    with app.app_context():
        response = _post(app, otp_payload(code="483920", email="priya@example.com"))

        assert response.status_code == 200
        assert response.get_json() == {"ok": True}
        assert len(_sent(app)) == 1
        email = _sent(app)[0]
        assert email["to"] == "priya@example.com"
        assert email["subject"] == "Your BCA Oslo verification code"
        assert "483920" in email["html"] and "483920" in email["text"]
        assert "483920" not in email["subject"]
        assert [a["content_id"] for a in email["attachments"]] == ["site-logo"]


def test_send_magic_link_forget_password_sends_the_branded_reset_email():
    app = _app()
    with app.app_context():
        url = "https://ep-test.aws.neon.tech/neondb/auth/reset-password/tok123?callbackURL=http://localhost:5173/reset-password"
        response = _post(app, magic_link_payload(link_url=url))

        assert response.status_code == 200
        email = _sent(app)[0]
        assert email["subject"] == "Reset your BCA Oslo password"
        assert url in email["text"]
        assert "Reset my password" in email["html"]
        assert "tok123" not in email["subject"]


def test_returns_404_and_sends_nothing_when_neon_auth_is_not_configured():
    app = _app(auth_url="")
    with app.app_context():
        response = _post(app, otp_payload())

        assert response.status_code == 404
        assert _sent(app) == []


def test_returns_404_and_sends_nothing_when_the_auth_provider_is_not_neon():
    # M1: a stray AUTH_URL (e.g. a production .env copied from .env.example) must not be
    # enough to switch the route on — the provider has to be "neon" as well.
    app = _app(auth_provider="supabase")
    with app.app_context():
        assert app.config["AUTH_URL"]
        response = _post(app, otp_payload())

        assert response.status_code == 404
        assert _sent(app) == []


def test_rejects_a_bad_signature_with_401_and_sends_nothing():
    app = _app()
    with app.app_context():
        response = _post(app, otp_payload(), key=ed25519.Ed25519PrivateKey.generate())

        assert response.status_code == 401
        assert _sent(app) == []


def test_rejects_a_stale_timestamp_with_401():
    app = _app()
    with app.app_context():
        stale = int(time.time() * 1000) - 6 * 60 * 1000
        response = _post(app, otp_payload(), timestamp_ms=stale)

        assert response.status_code == 401
        assert _sent(app) == []


def test_returns_503_so_neon_retries_when_the_signing_keys_cannot_be_fetched():
    # Review Focus #3
    app = _app()
    with app.app_context():
        response = _post(app, otp_payload(), jwks=UnreachableJWKClient())

        assert response.status_code == 503
        assert _sent(app) == []


def test_signed_but_malformed_payloads_get_400():
    app = _app()
    with app.app_context():
        assert _post(app, b"not json").status_code == 400
        assert _post(app, b"[1, 2]").status_code == 400
        no_email = otp_payload()
        del no_email["user"]["email"]
        assert _post(app, no_email).status_code == 400
        no_code = otp_payload()
        del no_code["event_data"]["otp_code"]
        assert _post(app, no_code).status_code == 400
        assert _post(app, magic_link_payload(link_url="javascript:alert(1)")).status_code == 400
        assert _sent(app) == []


def test_unsupported_events_types_and_sms_delivery_get_422_and_send_nothing():
    app = _app()
    with app.app_context():
        assert _post(app, otp_payload(otp_type="forget-password")).status_code == 422
        assert _post(app, otp_payload(otp_type="sign-in")).status_code == 422
        assert _post(app, otp_payload(delivery_preference="sms")).status_code == 422
        assert _post(app, magic_link_payload(link_type="email-verification")).status_code == 422
        other = otp_payload()
        other["event_type"] = "user.created"
        assert _post(app, other).status_code == 422
        assert _sent(app) == []


def test_an_email_service_failure_returns_500_so_neon_retries():
    app = _app()
    with app.app_context():
        def boom(**_kwargs):
            raise EmailServiceError("Failed to send email")

        with patch.object(app.extensions["email_service"], "send_email", side_effect=boom):
            assert _post(app, otp_payload()).status_code == 500
        with patch.object(
            app.extensions["email_service"],
            "send_email",
            side_effect=EmailServiceNotConfiguredError("not configured"),
        ):
            assert _post(app, otp_payload()).status_code == 500


def test_the_same_delivery_arriving_twice_just_sends_twice():
    # Review Focus #4: Neon retries reuse the event id; we deliberately do not dedupe (the code
    # is identical, so a duplicate email is harmless) — but it must not error.
    app = _app()
    with app.app_context():
        payload = otp_payload(event_id="evt-same")
        assert _post(app, payload).status_code == 200
        assert _post(app, payload).status_code == 200
        assert len(_sent(app)) == 2


def test_logs_the_event_and_type_but_never_the_code_link_token_or_address(caplog):
    caplog.set_level(logging.INFO)
    app = _app()
    with app.app_context():
        _post(app, otp_payload(code="483920", email="secret.person@example.com", event_id="evt-log-1"))
        _post(app, magic_link_payload(email="secret.person@example.com", event_id="evt-log-2"))

    assert "evt-log-1" in caplog.text and "send.otp" in caplog.text and "email-verification" in caplog.text
    assert "evt-log-2" in caplog.text and "forget-password" in caplog.text
    for secret in ("483920", "secret.person@example.com", "tok123", "reset-password/tok123"):
        assert secret not in caplog.text


def test_invalid_ipv6_in_link_url_gets_400():
    # Issue #1: urlparse("http://[abc") raises ValueError; must be caught and return 400, not 500
    app = _app()
    with app.app_context():
        assert _post(app, magic_link_payload(link_url="http://[abc")).status_code == 400
        assert _sent(app) == []


def test_link_url_with_scheme_but_no_netloc_gets_400():
    # Issue #1: "https:" passes scheme check but has no host; must be rejected as 400
    app = _app()
    with app.app_context():
        assert _post(app, magic_link_payload(link_url="https:")).status_code == 400
        assert _sent(app) == []


def test_non_string_expires_at_with_otp_degrades_gracefully():
    # Issue #2: non-string expires_at must not crash the route; template will omit expiry sentence
    app = _app()
    with app.app_context():
        for non_string_expires_at in (1789000000, ["x"], {"a": 1}, True):
            _sent(app).clear()
            response = _post(app, otp_payload(expires_at=non_string_expires_at))
            assert response.status_code == 200
            assert len(_sent(app)) == 1
            email = _sent(app)[0]
            assert "123456" in email["html"] and "123456" in email["text"]
            # The expiry sentence should NOT appear
            assert "expires in" not in email["html"].lower()
            assert "expires in" not in email["text"].lower()


def test_non_string_expires_at_with_magic_link_degrades_gracefully():
    # Issue #2: non-string expires_at must not crash the route for magic links either
    app = _app()
    with app.app_context():
        for non_string_expires_at in (1789000000, ["x"], {"a": 1}, True):
            _sent(app).clear()
            url = "https://example.com/reset?token=tok123"
            response = _post(app, magic_link_payload(link_url=url, expires_at=non_string_expires_at))
            assert response.status_code == 200
            assert len(_sent(app)) == 1
            email = _sent(app)[0]
            # The expiry sentence should NOT appear
            assert "expires in" not in email["html"].lower()
            assert "expires in" not in email["text"].lower()


def test_a_400_for_an_invalid_email_is_still_logged_without_the_address(caplog):
    # F2: the "received" line is the only trace of what Neon sent, so it must be written even
    # when the payload is then rejected — and never with the address in it.
    caplog.set_level(logging.INFO)
    app = _app()
    with app.app_context():
        response = _post(app, otp_payload(email="not-an-email", event_id="evt-bad-email"))

        assert response.status_code == 400
        assert _sent(app) == []

    assert "evt-bad-email" in caplog.text and "send.otp" in caplog.text
    assert "email-verification" in caplog.text
    assert "not-an-email" not in caplog.text
    assert "malformed" in caplog.text


def test_a_400_for_a_missing_otp_code_is_still_logged(caplog):
    caplog.set_level(logging.INFO)
    app = _app()
    with app.app_context():
        payload = otp_payload(event_id="evt-no-code", code="483920")
        del payload["event_data"]["otp_code"]
        response = _post(app, payload)

        assert response.status_code == 400

    assert "evt-no-code" in caplog.text and "send.otp" in caplog.text
    assert "malformed" in caplog.text
    assert "483920" not in caplog.text


def test_a_400_for_a_bad_link_url_is_logged_without_the_link(caplog):
    caplog.set_level(logging.INFO)
    app = _app()
    with app.app_context():
        response = _post(
            app, magic_link_payload(link_url="javascript:alert(1)", event_id="evt-bad-link")
        )

        assert response.status_code == 400

    assert "evt-bad-link" in caplog.text and "forget-password" in caplog.text
    assert "malformed" in caplog.text
    assert "javascript:alert(1)" not in caplog.text


def test_a_400_for_a_body_that_is_not_json_or_not_an_object_leaves_a_warning(caplog):
    caplog.set_level(logging.INFO)
    app = _app()
    with app.app_context():
        assert _post(app, b"not json").status_code == 400
        assert caplog.text.count("malformed") == 1
        assert _post(app, b"[1, 2]").status_code == 400
        assert caplog.text.count("malformed") == 2
