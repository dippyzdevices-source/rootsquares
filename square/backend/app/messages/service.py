"""Making a message ready, sending it and keeping the do-not-contact list.

Sending: `queue_message` works the audience out once and writes one `message_recipients` row per person (opted-out people are marked skipped for an
"update"); `run_send` then mails the queued rows one by one, committing after each, so a stopped worker resumes exactly where it was and nobody is
mailed twice. No queue or broker, same simple infrastructure as the newsletter (app/newsletter/service.py).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote

from flask import current_app

from app.audit.service import log_action
from app.auth.models import User
from app.common.urls import frontend_base_url
from app.email.templates import render_message_email
from app.extensions import db
from app.messages import audiences
from app.messages.audiences import Recipient
from app.messages.channels import get_channel
from app.messages.models import Message, MessageRecipient, MessageSuppression
from app.settings.models import get_site_settings

# Resend's default limit is 2 requests/second; stay comfortably under it.
SEND_DELAY_SECONDS = 0.6
# A "sending" message untouched for this long is considered stalled and is resumed by the job.
STALL_SECONDS = 120
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


# ---- opt-out ------------------------------------------------------------------------------


def unsubscribe_token(email: str) -> str:
    """Stateless: the token is derived from the address and the server secret, so no token is stored and none can be guessed."""
    secret = str(current_app.config["SECRET_KEY"]).encode()
    return hmac.new(secret, b"messages-unsubscribe:" + email.strip().lower().encode(), hashlib.sha256).hexdigest()[:40]


def valid_unsubscribe(email: str, token: str) -> bool:
    return bool(email) and hmac.compare_digest(unsubscribe_token(email), token or "")


def unsubscribe_url(email: str) -> str:
    return f"{frontend_base_url()}/messages/unsubscribe?e={quote(email)}&t={unsubscribe_token(email)}"


def unsubscribe_headers(email: str) -> dict[str, str]:
    api_url = current_app.config.get("API_PUBLIC_URL", "")
    if not api_url:
        return {"List-Unsubscribe": f"<{unsubscribe_url(email)}>"}
    return {
        "List-Unsubscribe": f"<{api_url}/api/messages/unsubscribe?e={quote(email)}&t={unsubscribe_token(email)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def suppress(email: str) -> bool:
    """Put the address on the do-not-contact list; returns True when it was new. One opt-out for everything we send (W14-R17): a newsletter
    subscriber with this address is marked unsubscribed too, so leaving anywhere is leaving everywhere."""
    from app.newsletter.models import Subscriber

    address = email.strip().lower()
    if not address:
        return False
    subscriber = Subscriber.query.filter_by(email=address).first()
    if subscriber is not None and subscriber.status != "unsubscribed":
        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(timezone.utc)
    new = MessageSuppression.query.filter_by(email=address).first() is None
    if new:
        db.session.add(MessageSuppression(email=address))
    db.session.commit()
    return new


def unsuppress(email: str) -> None:
    """The person chose to hear from us again (they subscribed on the website): take the address off the do-not-contact list."""
    MessageSuppression.query.filter_by(email=email.strip().lower()).delete()
    db.session.commit()


def suppressed_addresses(addresses: list[str]) -> set[str]:
    if not addresses:
        return set()
    rows = MessageSuppression.query.filter(MessageSuppression.email.in_(addresses)).all()
    return {r.email for r in rows}


# ---- placeholders -------------------------------------------------------------------------


def fill(text: str, context: dict, *, html: bool) -> str:
    """Replace {{name}}-style placeholders from the person's context; an unknown placeholder becomes empty."""

    def value(match: re.Match) -> str:
        found = str(context.get(match.group(1), ""))
        return escape(found) if html else found

    return PLACEHOLDER.sub(value, text)


# ---- queueing -----------------------------------------------------------------------------


def preview(audience: dict, kind: str) -> dict:
    people = audiences.resolve(audience)
    skipped = len(suppressed_addresses([p.email for p in people])) if kind == "update" else 0
    return {"total": len(people), "skipped": skipped, "will_receive": len(people) - skipped}


def queue_recipients(message: Message, people: list[Recipient], extra_context: dict | None = None) -> int:
    """Write the recipient rows (replacing any earlier run) and set the counters. Returns how many will actually be mailed."""
    MessageRecipient.query.filter_by(message_id=message.id).delete()
    opted_out = suppressed_addresses([p.email for p in people]) if message.kind == "update" else set()
    queued = 0
    for person in people:
        skipped = person.email in opted_out
        context = {"name": person.name, **(extra_context or {}), **person.context}
        db.session.add(
            MessageRecipient(message_id=message.id, email=person.email, name=person.name, context=context, status="skipped" if skipped else "queued")
        )
        queued += 0 if skipped else 1
    message.recipients_total = len(people)
    message.skipped_count = len(people) - queued
    message.sent_count = 0
    message.failed_count = 0
    db.session.commit()
    return queued


def queue_message(message: Message) -> int:
    return queue_recipients(message, audiences.resolve(message.audience or {}))


def _render(message: Message, recipient: MessageRecipient) -> tuple[str, str, str, list[dict], dict | None]:
    subject = fill(message.subject, recipient.context or {}, html=False)
    body = fill(message.body_html, recipient.context or {}, html=True)
    link = unsubscribe_url(recipient.email) if message.kind == "update" else None
    settings = get_site_settings()
    own_footer = settings.message_footer_update if message.kind == "update" else settings.message_footer_service
    html_body, text_body, attachments = render_message_email(subject=subject, body_html=body, kind=message.kind, unsubscribe_url=link, footer_text_override=own_footer or "")
    headers = unsubscribe_headers(recipient.email) if link else None
    return subject, html_body, text_body, attachments, headers


def send_test(message: Message, to: str) -> None:
    sample = MessageRecipient(message_id=message.id, email=to, name="", context={"name": "Sample name"}, status="queued")
    subject, html_body, text_body, attachments, headers = _render(message, sample)
    get_channel(message.channel).send(to=to, subject=f"[Test] {subject}", html=html_body, text=text_body, headers=headers, attachments=attachments)


# ---- sending ------------------------------------------------------------------------------


def run_send(message_id: int, delay: float = SEND_DELAY_SECONDS) -> None:
    """Mail every still-queued recipient, then mark the message sent. Needs an app context. One failure is counted and logged (never the address)."""
    message = db.session.get(Message, message_id)
    if message is None or message.status != "sending":
        return
    channel = get_channel(message.channel)
    while True:
        recipient = (
            MessageRecipient.query.filter_by(message_id=message.id, status="queued").order_by(MessageRecipient.id).first()
        )
        if recipient is None:
            break
        # Claim the row, so two workers on the same message never mail the same person twice.
        claimed = MessageRecipient.query.filter_by(id=recipient.id, status="queued").update({"status": "sending"}, synchronize_session=False)
        db.session.commit()
        if not claimed:
            continue
        db.session.refresh(recipient)
        try:
            subject, html_body, text_body, attachments, headers = _render(message, recipient)
            channel.send(to=recipient.email, subject=subject, html=html_body, text=text_body, headers=headers, attachments=attachments)
            recipient.status = "sent"
            message.sent_count += 1
        except Exception as exc:  # noqa: BLE001 - one bad address must not stop the rest
            recipient.status = "failed"
            message.failed_count += 1
            current_app.logger.error("Message %s: send failed for recipient %s: %s", message.id, recipient.id, exc)
        db.session.commit()
        if delay:
            time.sleep(delay)
    message.status = "sent"
    message.sent_at = datetime.now(timezone.utc)
    db.session.commit()


def start_sending(message_id: int) -> None:
    """Inline under TESTING (deterministic tests); a daemon thread otherwise."""
    app = current_app._get_current_object()
    if app.config["TESTING"]:
        run_send(message_id, delay=0)
        return

    def target():
        with app.app_context():
            try:
                run_send(message_id)
            except Exception:  # noqa: BLE001 - leave the message "sending"; the job resumes it
                app.logger.exception("Message send crashed for message %s", message_id)

    threading.Thread(target=target, daemon=True).start()


NEWSLETTER_AUDIENCE = "subscribers"  # a message to the newsletter subscribers is "a newsletter" (the audience key in app/messages/audiences.py)
OWN_DOMAIN_REQUIRED = "A newsletter is sent only from your own sending domain. Add it on your square's page at rootsquares and wait until it is verified."


def newsletter_blocked(message: Message) -> bool:
    """A newsletter may not be sent until the square's own sending domain is verified (ADR 091): bulk mail from the shared domain would put the reputation of every
    square at risk. Other messages are not affected. Nothing is enforced when no square is served."""
    from app.email.service import own_sending_domain_verified

    return (message.audience or {}).get("type") == NEWSLETTER_AUDIENCE and not own_sending_domain_verified()


def begin(message: Message, sender: User | None) -> bool:
    """Queue the audience and start sending. False (and back to draft) when nobody would receive it."""
    queued = queue_message(message)
    if queued == 0:
        message.status = "draft"
        db.session.commit()
        return False
    message.status = "sending"
    if sender is not None:
        message.sent_by_user_id = sender.id
    db.session.commit()
    if sender is not None:
        log_action(sender, "message_sent", f"Sent message #{message.id} ({message.kind}) to {queued} recipient(s)", target_type="message", target_id=message.id)
    start_sending(message.id)
    return True


def fire_due_messages() -> int:
    """Start every scheduled message whose time has come (claimed atomically) and resume stalled ones. Returns how many were started."""
    now = datetime.now(timezone.utc)
    due_ids = [i for (i,) in db.session.query(Message.id).filter(Message.status == "scheduled", Message.scheduled_for <= now).order_by(Message.scheduled_for).all()]
    started = 0
    for message_id in due_ids:
        claimed = Message.query.filter(Message.id == message_id, Message.status == "scheduled").update({"status": "sending"}, synchronize_session=False)
        db.session.commit()
        if not claimed:
            continue
        message = db.session.get(Message, message_id)
        if newsletter_blocked(message):  # the domain was removed or lost after it was scheduled: back to draft, nothing is sent
            message.status = "draft"
            db.session.commit()
            current_app.logger.warning("Scheduled newsletter %s not sent: no verified own sending domain; back to draft", message_id)
            continue
        sender = db.session.get(User, message.sent_by_user_id) if message.sent_by_user_id else None
        # The people may have changed since it was scheduled, so the audience is worked out now.
        if queue_message(message) == 0:
            message.status = "draft"
            db.session.commit()
            current_app.logger.warning("Scheduled message %s had nobody to send to; back to draft", message_id)
            continue
        if sender is not None:
            log_action(sender, "message_sent", f"Sent scheduled message #{message.id} to {message.recipients_total - message.skipped_count} recipient(s)", target_type="message", target_id=message.id)
        start_sending(message_id)
        started += 1
    stalled = now - timedelta(seconds=STALL_SECONDS)
    for message in Message.query.filter(Message.status == "sending", Message.updated_at < stalled).all():
        # A recipient still "sending" after the stall time was cut off by a crash: put it back in the queue.
        MessageRecipient.query.filter_by(message_id=message.id, status="sending").update({"status": "queued"}, synchronize_session=False)
        db.session.commit()
        if MessageRecipient.query.filter_by(message_id=message.id, status="queued").first():
            start_sending(message.id)
    return started
