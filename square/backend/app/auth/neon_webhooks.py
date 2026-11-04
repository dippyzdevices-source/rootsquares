"""Receives Neon Auth (Managed Better Auth) webhooks and delivers the emails Neon would
otherwise send itself — through our own EmailService (Resend) with our own templates.

Deliberately NOT protected by require_auth/require_role: Neon's signature (see
app.auth.webhook_verification) is the authentication. Inert unless AUTH_PROVIDER is "neon"
AND AUTH_URL is set; an environment authenticating against Supabase 404s here — no single
stray variable can switch it on.

Spec: docs/superpowers/specs/2026-09-24-neon-auth-email-webhook-design.md
"""

import json
from app.common.site import site_name
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request

from app.auth.webhook_verification import (
    NeonWebhookError,
    NeonWebhookKeyUnavailable,
    verify_neon_webhook,
)
from app.email.service import EmailServiceError, get_email_service
from app.email.templates import render_password_reset_email, render_signup_code_email

neon_webhooks_bp = Blueprint("neon_webhooks", __name__, url_prefix="/api/webhooks")



def _bad_request(message: str):
    return jsonify({"error": message}), 400


def _malformed(event_id, reason: str, message: str):
    # `reason` is always a fixed string chosen here — never a payload value, so a rejected
    # payload can't leak a code, link, token or address into the log through this line.
    current_app.logger.warning("Neon webhook malformed event_id=%s reason=%s", event_id, reason)
    return _bad_request(message)


@neon_webhooks_bp.post("/neon-auth")
def neon_auth_webhook():
    auth_url = current_app.config.get("AUTH_URL", "")
    if current_app.config.get("AUTH_PROVIDER") != "neon" or not auth_url:
        return jsonify({"error": "Not found"}), 404

    # The signature is over the exact bytes Neon sent, so read them before any JSON parsing.
    raw_body = request.get_data()
    try:
        verify_neon_webhook(raw_body, request.headers, auth_url)
    except NeonWebhookKeyUnavailable:
        current_app.logger.error("Neon webhook could not be verified: signing keys unavailable")
        return jsonify({"error": "Signing keys unavailable"}), 503
    except NeonWebhookError as exc:
        current_app.logger.warning("Neon webhook rejected: %s", exc)
        return jsonify({"error": "Invalid webhook"}), 401

    try:
        payload = json.loads(raw_body)
    except ValueError:
        current_app.logger.warning("Neon webhook malformed reason=body is not valid JSON")
        return _bad_request("Body is not valid JSON")
    if not isinstance(payload, dict):
        current_app.logger.warning("Neon webhook malformed reason=body is not a JSON object")
        return _bad_request("Body must be a JSON object")

    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    event_data = payload.get("event_data")
    user = payload.get("user")
    if isinstance(event_data, dict):
        kind = event_data.get("otp_type") if event_type == "send.otp" else event_data.get("link_type")
    else:
        kind = None
    # This line is the only trace of what Neon actually sent (Neon offers no event log or
    # redelivery) — so it is written for every request that gets this far, including the ones
    # rejected below. Never add the code, link, token or address to it.
    current_app.logger.info(
        "Neon webhook received event_id=%s event_type=%s type=%s", event_id, event_type, kind
    )

    if not isinstance(event_data, dict) or not isinstance(user, dict):
        return _malformed(event_id, "missing event_data or user", "Missing event_data or user")
    email = user.get("email")
    if not isinstance(email, str) or "@" not in email:
        return _malformed(event_id, "missing user email", "Missing user email")

    expires_at = event_data.get("expires_at")
    # Coerce non-string expires_at to None so templates can omit expiry sentence gracefully
    expires_at = expires_at if isinstance(expires_at, str) else None

    if (
        event_type == "send.otp"
        and kind == "email-verification"
        and event_data.get("delivery_preference") in (None, "email")
    ):
        code = event_data.get("otp_code")
        if not isinstance(code, str) or not code:
            return _malformed(event_id, "missing otp_code", "Missing otp_code")
        subject = f"Your {site_name()} verification code"
        html_body, text_body, attachments = render_signup_code_email(code=code, expires_at=expires_at)
    elif event_type == "send.magic_link" and kind == "forget-password":
        link_url = event_data.get("link_url")
        if not isinstance(link_url, str):
            return _malformed(event_id, "missing or invalid link_url", "Missing or invalid link_url")
        try:
            parsed = urlparse(link_url)
        except ValueError:
            return _malformed(event_id, "missing or invalid link_url", "Missing or invalid link_url")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return _malformed(event_id, "missing or invalid link_url", "Missing or invalid link_url")
        subject = f"Reset your {site_name()} password"
        html_body, text_body, attachments = render_password_reset_email(
            reset_url=link_url, expires_at=expires_at
        )
    else:
        # 422 (non-retryable) on purpose: the user sees an error now instead of waiting for an
        # email that will never come. If a real Neon flow lands here, the log line above says
        # which (event, type) it was — add a branch for it.
        current_app.logger.error(
            "Neon webhook has no handler event_id=%s event_type=%s type=%s", event_id, event_type, kind
        )
        return jsonify({"error": "Unsupported event"}), 422

    try:
        get_email_service().send_email(
            to=email, subject=subject, html=html_body, text=text_body, attachments=attachments
        )
    except EmailServiceError as exc:
        # Unlike the order emails (app.orders.emails), a failed send must NOT be swallowed here:
        # the user would never get their code while Neon believes delivery succeeded. 500 makes
        # Neon retry.
        current_app.logger.error("Neon webhook email failed event_id=%s error=%s", event_id, exc)
        return jsonify({"error": "Email delivery failed"}), 500

    return jsonify({"ok": True})
