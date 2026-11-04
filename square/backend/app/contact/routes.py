"""Public Contact Us submission — validates input, applies lightweight abuse protection, and
sends a notification email to CONTACT_EMAIL via EmailService (see app.email.service). No
ContactMessage model/table exists (nothing in this project required persisting these yet) —
sending the email is the whole feature for now; a future story can add a ContactMessage table
without touching EmailService or this route's validation.
"""

import re
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from app.common.site import site_name
from app.email.service import (
    EmailServiceError,
    EmailServiceNotConfiguredError,
    contact_recipients,
    get_email_service,
)
from app.email.templates import render_contact_submission_email

contact_bp = Blueprint("contact", __name__, url_prefix="/api/contact")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 255
MAX_SUBJECT_LENGTH = 200
MAX_MESSAGE_LENGTH = 5000
MIN_MESSAGE_LENGTH = 10

# In-memory, per-process rate limiting — this app has no Redis/shared cache (see CLAUDE.md's
# "modular monolith" rule), so a small in-memory window is the proportionate choice for a
# single public endpoint rather than introducing infrastructure just for this. Resets on
# restart and isn't shared across worker processes — an accepted, documented limitation, not a
# hard guarantee against a determined attacker.
_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_RATE_LIMIT_MAX_REQUESTS = 5
_submission_log: dict[str, list[float]] = {}


def _client_ip() -> str:
    # Render (and most PaaS hosts) put the real client IP in X-Forwarded-For behind a proxy.
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _submission_log.get(ip, []) if now - t < _RATE_LIMIT_WINDOW_SECONDS]
    _submission_log[ip] = recent
    if len(recent) >= _RATE_LIMIT_MAX_REQUESTS:
        return True
    recent.append(now)
    return False


def _validate(data: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "This field is required."
    elif len(name.strip()) > MAX_NAME_LENGTH:
        errors["name"] = f"Must be at most {MAX_NAME_LENGTH} characters."
    else:
        cleaned["name"] = name.strip()

    email = data.get("email")
    if not isinstance(email, str) or not email.strip():
        errors["email"] = "This field is required."
    elif len(email.strip()) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email.strip()):
        errors["email"] = "Enter a valid email address."
    else:
        cleaned["email"] = email.strip()

    subject = data.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        errors["subject"] = "This field is required."
    elif len(subject.strip()) > MAX_SUBJECT_LENGTH:
        errors["subject"] = f"Must be at most {MAX_SUBJECT_LENGTH} characters."
    else:
        # Subject ends up in an email Subject header — strip any newline a client might send
        # to prevent header injection, regardless of what a well-behaved frontend would send.
        cleaned["subject"] = " ".join(subject.strip().splitlines())

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        errors["message"] = "This field is required."
    elif len(message.strip()) < MIN_MESSAGE_LENGTH:
        errors["message"] = f"Must be at least {MIN_MESSAGE_LENGTH} characters."
    elif len(message.strip()) > MAX_MESSAGE_LENGTH:
        errors["message"] = f"Must be at most {MAX_MESSAGE_LENGTH} characters."
    else:
        cleaned["message"] = message.strip()

    return cleaned, errors


@contact_bp.post("")
def submit_contact():
    data = request.get_json(silent=True) or {}

    # Honeypot: a hidden field real visitors never fill in. Bots that blindly fill every form
    # field trip it — respond exactly like a real success so the bot learns nothing, but never
    # actually send the email.
    if isinstance(data.get("website"), str) and data.get("website").strip():
        return jsonify({"success": True, "message": "Your message has been sent successfully."})

    ip = _client_ip()
    if _is_rate_limited(ip):
        return jsonify({"error": "Too many messages sent recently. Please try again later."}), 429

    cleaned, errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    recipients = contact_recipients()
    if not recipients:
        current_app.logger.error("Contact form submitted but the square has no contact e-mail and CONTACT_EMAIL is not configured.")
        return jsonify({"error": "We couldn't send your message right now. Please try again later."}), 503

    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_body, text_body, attachments = render_contact_submission_email(
        name=cleaned["name"],
        email=cleaned["email"],
        subject=cleaned["subject"],
        message=cleaned["message"],
        submitted_at=submitted_at,
    )

    try:
        get_email_service().send_email(
            to=recipients,
            subject=f"[{site_name()}] {cleaned['subject']}",
            html=html_body,
            text=text_body,
            reply_to=cleaned["email"],
            attachments=attachments,
        )
    except (EmailServiceError, EmailServiceNotConfiguredError) as exc:
        current_app.logger.error("Contact form email failed to send: %s", exc)
        return jsonify({"error": "We couldn't send your message right now. Please try again later."}), 503

    return jsonify({"success": True, "message": "Your message has been sent successfully."})
