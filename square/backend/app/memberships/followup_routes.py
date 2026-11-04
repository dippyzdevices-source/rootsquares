"""Admin follow-up on unpaid memberships — two groups of people an admin may want to nudge:

* **requests**: members who asked for a membership but haven't paid its first period yet (these
  are hidden from the approval lists — see app.memberships.service.awaiting_payment_clause);
* **dues**: members whose membership is active but who have unpaid periods that have started.

A reminder is a real email (best done from here, so the admin sees an error if it fails). There is
no extra column for "last reminded": each send is written to the audit log, and the newest such row
for a membership is what the list and the 3-day cooldown read.
"""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import func

from app.common.money import format_money
from app.common.site import site_currency, site_name
from app.audit.models import AuditLog
from app.audit.service import log_action
from app.auth.decorators import require_role
from app.common.urls import frontend_base_url
from app.email.service import get_email_service
from app.email.templates import render_membership_reminder_email
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from app.memberships.service import (
    awaiting_payment_clause,
    current_period_for_date,
    discard_pending_request,
    due_periods,
    has_live_payment,
    is_awaiting_payment,
)

admin_membership_followup_bp = Blueprint(
    "admin_membership_followup", __name__, url_prefix="/api/admin/membership-follow-up"
)
admin_membership_followup_bp.before_request(require_role("admin"))

REMINDER_ACTION = "membership_reminder_sent"
REMINDER_COOLDOWN_DAYS = 3
MAX_PERIODS_IN_EMAIL = 6


def _kr(amount_ore: int) -> str:
    return format_money(amount_ore, site_currency(), whole_if_round=True)


def _contact_of(member: Member) -> tuple:
    email = member.user.email if member.user else member.email
    phone = member.user.phone if member.user and member.user.phone else member.phone
    return email, phone


def _person(member: Member) -> dict:
    # A child has no email/login of their own: reach them through their parent.
    email, phone = _contact_of(member)
    parent = member.parent if member.parent_member_id else None
    if parent is not None:
        parent_email, parent_phone = _contact_of(parent)
        email, phone = email or parent_email, phone or parent_phone
    return {
        "member_id": member.id,
        "name": member.name,
        "email": email,
        "phone": phone,
        "parent_name": parent.name if parent is not None else None,
    }


def _last_reminded(membership_ids: list[int]) -> dict[int, datetime]:
    if not membership_ids:
        return {}
    rows = (
        db.session.query(AuditLog.target_id, func.max(AuditLog.created_at))
        .filter(
            AuditLog.action == REMINDER_ACTION,
            AuditLog.target_type == "membership",
            AuditLog.target_id.in_(membership_ids),
        )
        .group_by(AuditLog.target_id)
        .all()
    )
    return {target_id: when for target_id, when in rows}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _reminder_fields(membership_id: int, last: dict[int, datetime], now: datetime) -> dict:
    when = last.get(membership_id)
    if when is None:
        return {"last_reminded_at": None, "can_remind": True}
    when = _aware(when)
    return {
        "last_reminded_at": when.isoformat(),
        "can_remind": now - when >= timedelta(days=REMINDER_COOLDOWN_DAYS),
    }


@admin_membership_followup_bp.get("")
def list_follow_ups():
    today = date.today()
    now = datetime.now(timezone.utc)

    requests = (
        Membership.query.filter(awaiting_payment_clause())
        .order_by(Membership.created_at.asc())
        .all()
    )
    actives = Membership.query.filter_by(status="active").all()
    due_rows = []
    for membership in actives:
        periods = due_periods(membership, today)
        if periods:
            due_rows.append((membership, periods))

    last = _last_reminded([m.id for m in requests] + [m.id for m, _ in due_rows])

    request_items = []
    for membership in requests:
        current = current_period_for_date(membership, today)
        created = _aware(membership.created_at) if membership.created_at else now
        request_items.append(
            {
                "membership_id": membership.id,
                **_person(membership.member),
                "membership_type": membership.membership_type,
                "period_label": current.label if current else None,
                "amount": current.amount if current else 0,
                "requested_at": created.isoformat(),
                "days_waiting": max((now - created).days, 0),
                **_reminder_fields(membership.id, last, now),
            }
        )

    due_items = []
    for membership, periods in due_rows:
        oldest = periods[0]
        due_items.append(
            {
                "membership_id": membership.id,
                **_person(membership.member),
                "membership_type": membership.membership_type,
                "due_count": len(periods),
                "due_total": sum(p.amount for p in periods),
                "due_labels": [p.label for p in periods],
                "days_overdue": max((today - oldest.period_start).days, 0),
                **_reminder_fields(membership.id, last, now),
            }
        )
    due_items.sort(key=lambda row: row["days_overdue"], reverse=True)

    return jsonify({"requests": request_items, "dues": due_items})


@admin_membership_followup_bp.post("/<int:membership_id>/reminder")
def send_reminder(membership_id: int):
    membership = db.session.get(Membership, membership_id)
    if membership is None:
        return jsonify({"error": "Membership not found"}), 404

    today = date.today()
    if is_awaiting_payment(membership):
        current = current_period_for_date(membership, today)
        if current is None:
            return jsonify({"error": "Nothing is waiting for payment."}), 409
        kind = "request"
        lines = [(current.label, _kr(current.amount))]
        total = current.amount
    elif membership.status == "active" and (periods := due_periods(membership, today)):
        kind = "dues"
        lines = [(p.label, _kr(p.amount)) for p in periods[:MAX_PERIODS_IN_EMAIL]]
        if len(periods) > MAX_PERIODS_IN_EMAIL:
            lines.append((f"and {len(periods) - MAX_PERIODS_IN_EMAIL} more", ""))
        total = sum(p.amount for p in periods)
    else:
        return jsonify({"error": "Nothing is waiting for payment."}), 409

    member = membership.member
    person = _person(member)
    if not person["email"]:
        return jsonify({"error": "This member has no email address."}), 400

    now = datetime.now(timezone.utc)
    last = _last_reminded([membership.id])
    if not _reminder_fields(membership.id, last, now)["can_remind"]:
        return jsonify(
            {"error": f"A reminder was already sent in the last {REMINDER_COOLDOWN_DAYS} days."}
        ), 409

    try:
        html_body, text_body, attachments = render_membership_reminder_email(
            name=person["parent_name"] or member.name,
            child_name=member.name if person["parent_name"] else None,
            kind=kind,
            membership_type=membership.membership_type,
            lines=lines,
            total_text=_kr(total),
            dashboard_url=f"{frontend_base_url()}/member",
        )
        get_email_service().send_email(
            to=person["email"],
            subject=(
                f"Your {site_name()} membership is waiting for payment"
                if kind == "request"
                else f"A reminder: your {site_name()} membership payment is due"
            ),
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
    except Exception as exc:  # noqa: BLE001 - tell the admin, never the address
        current_app.logger.error("Membership reminder email failed: %s", exc)
        return jsonify({"error": "Could not send the email. Please try again."}), 502

    log_action(
        g.current_user,
        REMINDER_ACTION,
        f"Sent a payment reminder to {member.name} ({kind})",
        target_type="membership",
        target_id=membership.id,
    )
    return jsonify({"status": "sent", "last_reminded_at": now.isoformat()})


@admin_membership_followup_bp.delete("/<int:membership_id>")
def remove_request(membership_id: int):
    """Clears a stale, unpaid request. Never touches an active membership or one with a payment."""
    membership = db.session.get(Membership, membership_id)
    if membership is None:
        return jsonify({"error": "Membership not found"}), 404
    if not is_awaiting_payment(membership):
        return jsonify({"error": "Only a request that is waiting for its first payment can be removed."}), 409
    if has_live_payment(membership):
        return jsonify({"error": "A payment is in progress for this request."}), 409

    name = membership.member.name
    discard_pending_request(membership)
    db.session.commit()
    log_action(
        g.current_user,
        "membership_request_removed",
        f"Removed the unpaid membership request of {name}",
        target_type="membership",
        target_id=membership_id,
    )
    return "", 204
