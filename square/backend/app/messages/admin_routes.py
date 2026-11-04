"""Admin side of the Messages module: compose, preview the audience, test, send or schedule; reminder rules; the do-not-contact list. Admin only."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.features import locked
from app.messages import audiences, rules, service
from app.messages.models import Message, MessageRecipient, MessageRule, MessageSuppression
from app.newsletter.admin_routes import sanitize_newsletter_content

admin_messages_bp = Blueprint("admin_messages", __name__, url_prefix="/api/admin/messages")
admin_messages_bp.before_request(require_role("admin"))

KINDS = ("update", "service")
MAX_SUBJECT = 200
MAX_BODY = 100_000
EDITABLE_STATUSES = ("draft",)


def _text_of(html: str) -> str:
    return re.sub(r"<[^>]*>", "", html or "").strip()


def _serialize(message: Message) -> dict:
    return {
        "id": message.id,
        "kind": message.kind,
        "channel": message.channel,
        "subject": message.subject,
        "body_html": message.body_html,
        "audience": message.audience,
        "status": message.status,
        "source": message.source,
        "recipients_total": message.recipients_total,
        "sent_count": message.sent_count,
        "failed_count": message.failed_count,
        "skipped_count": message.skipped_count,
        "scheduled_for": message.scheduled_for.isoformat() if message.scheduled_for else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "created_at": message.created_at.isoformat(),
    }


def _get(message_id: int):
    message = db.session.get(Message, message_id)
    if message is None:
        return None, (jsonify({"error": "Message not found"}), 404)
    return message, None


def _clean_payload(data: dict, *, existing: Message | None = None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    clean: dict = {}
    if "kind" in data or existing is None:
        if data.get("kind") not in KINDS:
            errors["kind"] = "Choose update or service."
        else:
            clean["kind"] = data["kind"]
    if "subject" in data or existing is None:
        subject = data.get("subject")
        if not isinstance(subject, str) or not subject.strip() or len(subject.strip()) > MAX_SUBJECT:
            errors["subject"] = f"Required, at most {MAX_SUBJECT} characters."
        else:
            clean["subject"] = subject.strip()
    if "body_html" in data or existing is None:
        body = data.get("body_html", "")
        if not isinstance(body, str) or len(body) > MAX_BODY:
            errors["body_html"] = "Too long."
        else:
            clean["body_html"] = sanitize_newsletter_content(body)
    if "audience" in data or existing is None:
        audience, error = audiences.validate_audience(data.get("audience"))
        if error:
            errors["audience"] = error
        else:
            clean["audience"] = audience
    return clean, errors


# ---- what can be chosen ---------------------------------------------------------------------


@admin_messages_bp.get("/options")
def options():
    """Everything the compose form offers: audiences of the modules that are on, the events to choose from, the reminder triggers."""
    from app.events.models import Event
    from app.modules import module_enabled

    events = []
    if module_enabled("events"):
        events = [{"id": e.id, "title": e.title, "start": e.start_datetime.isoformat()} for e in Event.query.order_by(Event.start_datetime.desc()).limit(200).all()]
    types = []
    if module_enabled("memberships"):
        from app.memberships.models import MembershipType

        types = [t.name for t in MembershipType.query.filter_by(is_active=True).order_by(MembershipType.name).all()]
    return jsonify(
        {
            "audiences": [
                {"key": a.key, "label": a.label, "description": a.description, "params": list(a.params)} for a in audiences.available_audiences()
            ],
            "events": events,
            "membership_types": types,
            "membership_statuses": ["active", "pending", "expired", "cancelled", "suspended"] if module_enabled("memberships") else [],
            "triggers": rules.available_triggers(),
        }
    )


@admin_messages_bp.post("/preview")
def preview_audience():
    data = request.get_json(silent=True) or {}
    audience, error = audiences.validate_audience(data.get("audience"))
    if error:
        return jsonify({"errors": {"audience": error}}), 400
    kind = data.get("kind") if data.get("kind") in KINDS else "update"
    return jsonify(service.preview(audience, kind))


# ---- messages -------------------------------------------------------------------------------


@admin_messages_bp.get("")
def list_messages():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 25, type=int), 1), 50)
    query = Message.query.order_by(Message.created_at.desc(), Message.id.desc())
    audience_type = request.args.get("audience")
    if audience_type:
        # the Newsletters tab (W14-R19): only the messages sent to one audience; `audience` is a JSON column, so the filter is made here
        matching = [m for m in query.all() if (m.audience or {}).get("type") == audience_type]
        total = len(matching)
        rows = matching[(page - 1) * per_page : page * per_page]
    else:
        total = query.count()
        rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({"items": [_serialize(m) for m in rows], "total": total, "page": page, "per_page": per_page})


@admin_messages_bp.post("")
def create_message():
    clean, errors = _clean_payload(request.get_json(silent=True) or {})
    if errors:
        return jsonify({"errors": errors}), 400
    message = Message(**clean)
    db.session.add(message)
    db.session.commit()
    return jsonify(_serialize(message)), 201


@admin_messages_bp.get("/<int:message_id>")
def get_message(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    return jsonify(_serialize(message))


@admin_messages_bp.get("/<int:message_id>/recipients")
def message_recipients(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    status = request.args.get("status")
    page = max(request.args.get("page", 1, type=int), 1)
    query = MessageRecipient.query.filter_by(message_id=message.id)
    if status:
        query = query.filter_by(status=status)
    total = query.count()
    rows = query.order_by(MessageRecipient.id).offset((page - 1) * 50).limit(50).all()
    return jsonify({"items": [{"id": r.id, "email": r.email, "name": r.name, "status": r.status} for r in rows], "total": total, "page": page, "per_page": 50})


@admin_messages_bp.patch("/<int:message_id>")
def update_message(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    if message.status not in EDITABLE_STATUSES:
        return jsonify({"error": "Only a draft can be edited."}), 409
    clean, errors = _clean_payload(request.get_json(silent=True) or {}, existing=message)
    if errors:
        return jsonify({"errors": errors}), 400
    for field, value in clean.items():
        setattr(message, field, value)
    db.session.commit()
    return jsonify(_serialize(message))


@admin_messages_bp.delete("/<int:message_id>")
def delete_message(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    if message.status not in ("draft", "scheduled"):
        return jsonify({"error": "A message that has been sent is kept as a record."}), 409
    db.session.delete(message)
    db.session.commit()
    return "", 204


@admin_messages_bp.post("/<int:message_id>/send-test")
def send_test(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    to = (request.get_json(silent=True) or {}).get("to") or g.current_user.email
    if not isinstance(to, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", to.strip()):
        return jsonify({"errors": {"to": "Enter a valid e-mail address."}}), 400
    try:
        service.send_test(message, to.strip())
    except Exception:  # noqa: BLE001
        return jsonify({"error": "Could not send the test e-mail."}), 502
    return jsonify({"sent_to": to.strip()})


@admin_messages_bp.post("/<int:message_id>/send")
def send_message(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    if message.status != "draft":
        return jsonify({"error": "This message has already been sent or scheduled."}), 409
    if not message.subject.strip() or not _text_of(message.body_html):
        return jsonify({"error": "Add a subject and some content first."}), 400
    if service.newsletter_blocked(message):
        return jsonify({"error": service.OWN_DOMAIN_REQUIRED, "code": "own_domain_required"}), 409
    info = service.preview(message.audience or {}, message.kind)
    if info["will_receive"] == 0:
        return jsonify({"error": "Nobody would receive this message."}), 400
    raw = (request.get_json(silent=True) or {}).get("scheduled_for")
    if raw not in (None, ""):
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"errors": {"scheduled_for": "Not a valid date and time."}}), 400
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when <= datetime.now(timezone.utc):
            return jsonify({"errors": {"scheduled_for": "Choose a time in the future."}}), 400
        message.status = "scheduled"
        message.scheduled_for = when
        message.sent_by_user_id = g.current_user.id
        db.session.commit()
        log_action(g.current_user, "message_scheduled", f"Scheduled message #{message.id} for {when.strftime('%Y-%m-%d %H:%M')} UTC", target_type="message", target_id=message.id)
        return jsonify(_serialize(message)), 200
    if not service.begin(message, g.current_user):
        return jsonify({"error": "Nobody would receive this message."}), 400
    db.session.refresh(message)
    return jsonify(_serialize(message)), 202


@admin_messages_bp.post("/<int:message_id>/unschedule")
def unschedule(message_id: int):
    message, error = _get(message_id)
    if error:
        return error
    if message.status != "scheduled":
        return jsonify({"error": "This message is not scheduled."}), 409
    message.status = "draft"
    message.scheduled_for = None
    db.session.commit()
    return jsonify(_serialize(message))


# ---- reminder rules -------------------------------------------------------------------------


def _serialize_rule(rule: MessageRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "trigger": rule.trigger,
        "offset_days": rule.offset_days,
        "send_hour": rule.send_hour,
        "enabled": rule.enabled,
        "subject": rule.subject,
        "body_html": rule.body_html,
    }


def _clean_rule(data: dict, *, creating: bool) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    clean: dict = {}
    if "name" in data or creating:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            errors["name"] = "Required, at most 120 characters."
        else:
            clean["name"] = name.strip()
    if "trigger" in data or creating:
        trigger = data.get("trigger")
        spec = rules.TRIGGERS.get(trigger) if isinstance(trigger, str) else None
        if spec is None:
            errors["trigger"] = "Choose when the reminder is sent."
        else:
            from app.modules import module_enabled

            if not rules.trigger_available(spec):
                errors["trigger"] = "That reminder is not available."
            else:
                clean["trigger"] = trigger
    if "offset_days" in data or creating:
        days = data.get("offset_days")
        if not isinstance(days, int) or isinstance(days, bool) or not 0 <= days <= 365:
            errors["offset_days"] = "A number of days from 0 to 365."
        else:
            clean["offset_days"] = days
    if "send_hour" in data:
        hour = data.get("send_hour")
        if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
            errors["send_hour"] = "An hour from 0 to 23."
        else:
            clean["send_hour"] = hour
    if "enabled" in data:
        if not isinstance(data["enabled"], bool):
            errors["enabled"] = "Must be true or false."
        else:
            clean["enabled"] = data["enabled"]
    if "subject" in data or creating:
        subject = data.get("subject")
        if not isinstance(subject, str) or not subject.strip() or len(subject.strip()) > MAX_SUBJECT:
            errors["subject"] = f"Required, at most {MAX_SUBJECT} characters."
        else:
            clean["subject"] = subject.strip()
    if "body_html" in data or creating:
        body = data.get("body_html", "")
        if not isinstance(body, str) or len(body) > MAX_BODY or not _text_of(body):
            errors["body_html"] = "Add the text of the reminder."
        else:
            clean["body_html"] = sanitize_newsletter_content(body)
    return clean, errors


@admin_messages_bp.get("/rules")
def list_rules():
    return jsonify({"items": [_serialize_rule(r) for r in MessageRule.query.order_by(MessageRule.id).all()]})


@admin_messages_bp.post("/rules")
def create_rule():
    if (refused := locked("message_reminders")) is not None:
        return refused
    clean, errors = _clean_rule(request.get_json(silent=True) or {}, creating=True)
    if errors:
        return jsonify({"errors": errors}), 400
    rule = MessageRule(**clean)
    db.session.add(rule)
    db.session.commit()
    log_action(g.current_user, "message_rule_created", f"Created reminder rule #{rule.id}", target_type="message_rule", target_id=rule.id)
    return jsonify(_serialize_rule(rule)), 201


@admin_messages_bp.patch("/rules/<int:rule_id>")
def update_rule(rule_id: int):
    if (refused := locked("message_reminders")) is not None:
        return refused
    rule = db.session.get(MessageRule, rule_id)
    if rule is None:
        return jsonify({"error": "Rule not found"}), 404
    clean, errors = _clean_rule(request.get_json(silent=True) or {}, creating=False)
    if errors:
        return jsonify({"errors": errors}), 400
    for field, value in clean.items():
        setattr(rule, field, value)
    db.session.commit()
    return jsonify(_serialize_rule(rule))


@admin_messages_bp.delete("/rules/<int:rule_id>")
def delete_rule(rule_id: int):
    rule = db.session.get(MessageRule, rule_id)
    if rule is None:
        return jsonify({"error": "Rule not found"}), 404
    db.session.delete(rule)
    db.session.commit()
    log_action(g.current_user, "message_rule_deleted", f"Deleted reminder rule #{rule_id}", target_type="message_rule", target_id=rule_id)
    return "", 204


# ---- do-not-contact list --------------------------------------------------------------------


@admin_messages_bp.get("/suppressions")
def list_suppressions():
    rows = MessageSuppression.query.order_by(MessageSuppression.created_at.desc()).limit(500).all()
    return jsonify({"items": [{"id": r.id, "email": r.email, "created_at": r.created_at.isoformat()} for r in rows]})


@admin_messages_bp.post("/suppressions")
def add_suppression():
    emails = audiences.parse_addresses((request.get_json(silent=True) or {}).get("emails"))
    if not emails:
        return jsonify({"errors": {"emails": "Enter at least one valid e-mail address."}}), 400
    added = sum(1 for e in emails if service.suppress(e))
    log_action(g.current_user, "message_optout_added", f"Added {added} address(es) to the do-not-contact list")
    return jsonify({"added": added}), 201


@admin_messages_bp.delete("/suppressions/<int:suppression_id>")
def remove_suppression(suppression_id: int):
    row = db.session.get(MessageSuppression, suppression_id)
    if row is None:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(row)
    db.session.commit()
    log_action(g.current_user, "message_optout_removed", "Removed an address from the do-not-contact list")
    return "", 204
