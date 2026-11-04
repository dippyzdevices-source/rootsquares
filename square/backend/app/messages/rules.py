"""Automatic reminders (the second half of the Messages module). A rule says "N days before X, tell the people it concerns".

`run_rules` is called by the background job every minute and is idempotent: a (rule, target) pair is recorded first (a unique row), so a reminder is
made once even with several workers or restarts. A reminder is a "service" message (no opt-out: it is about something the person booked, bought or
joined). Each trigger gives the placeholders its text may use; `TRIGGERS` is the one place to add a new kind of reminder.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.common.money import format_money
from app.common.site import site_currency, site_timezone
from app.extensions import db
from app.features import feature_enabled
from app.messages import audiences
from app.messages.audiences import Recipient
from app.messages.models import Message, MessageRule, MessageRuleRun
from app.messages.service import queue_recipients, start_sending
from app.modules import module_enabled

# trigger key -> (label, the modules it needs, the placeholders its text may use)
EVENT_PLACEHOLDERS = ["name", "event_title", "event_date", "event_time", "event_venue"]
TRIGGERS: dict[str, dict] = {
    "event_before": {
        "label": "Before an event, to its ticket holders",
        "modules": ("events", "tickets"),
        "placeholders": EVENT_PLACEHOLDERS,
    },
    "event_before_members": {
        "label": "Before an event, to everyone on the member list",
        "modules": ("events", "members"),
        "placeholders": EVENT_PLACEHOLDERS,
    },
    "membership_ending": {
        "label": "Before a membership ends, to the member",
        "modules": ("memberships",),
        "placeholders": ["name", "membership_type", "end_date"],
    },
    "period_due": {
        "label": "Before a membership payment is due, to the member",
        "modules": ("memberships",),
        "placeholders": ["name", "period_label", "amount", "due_date"],
    },
}


def trigger_available(spec: dict) -> bool:
    """A trigger exists only while every module it needs is on."""
    return all(module_enabled(m) for m in spec["modules"])


def available_triggers() -> list[dict]:
    return [{"key": key, "label": spec["label"], "placeholders": spec["placeholders"]} for key, spec in TRIGGERS.items() if trigger_available(spec)]


def _pretty(day: date) -> str:
    return day.strftime("%d %b %Y").lstrip("0")


def _member_recipient(member, user_email: str | None) -> Recipient | None:
    address = (user_email or member.email or "").strip().lower()
    return Recipient(address, member.name) if address and member.erased_at is None and member.erase_requested_at is None else None


def _event_targets(rule: MessageRule, target: date):
    from app.events.models import Event

    zone = site_timezone()
    for event in Event.query.filter(Event.published.is_(True), Event.status != "cancelled").all():
        start = event.start_datetime.astimezone(zone)
        if start.date() != target:
            continue
        if rule.trigger == "event_before_members":
            people = audiences.resolve({"type": "members", "params": {}})
        else:
            people = audiences.resolve({"type": "ticket_holders", "params": {"event_id": event.id}})
        context = {
            "event_title": event.title,
            "event_date": _pretty(start.date()),
            "event_time": start.strftime("%H:%M"),
            "event_venue": event.venue or "",
        }
        yield f"event:{event.id}", people, context


def _ending_targets(rule: MessageRule, target: date):
    from app.auth.models import User
    from app.members.models import Member
    from app.memberships.models import Membership

    people = []
    rows = (
        db.session.query(Member, User.email, Membership)
        .join(Membership, Membership.member_id == Member.id)
        .outerjoin(User, Member.user_id == User.id)
        .filter(Membership.status == "active", Membership.end_date == target)
        .all()
    )
    for member, user_email, membership in rows:
        person = _member_recipient(member, user_email)
        if person:
            person.context = {"membership_type": membership.membership_type, "end_date": _pretty(target)}
            people.append(person)
    yield f"ending:{target.isoformat()}", people, {}


def _due_targets(rule: MessageRule, target: date):
    from app.auth.models import User
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipPeriod

    people = []
    rows = (
        db.session.query(Member, User.email, MembershipPeriod)
        .join(Membership, Membership.member_id == Member.id)
        .join(MembershipPeriod, MembershipPeriod.membership_id == Membership.id)
        .outerjoin(User, Member.user_id == User.id)
        .filter(Membership.status == "active", MembershipPeriod.status == "unpaid", MembershipPeriod.period_start == target)
        .all()
    )
    for member, user_email, period in rows:
        person = _member_recipient(member, user_email)
        if person:
            person.context = {"period_label": period.label, "amount": format_money(period.amount, period.currency or site_currency()), "due_date": _pretty(target)}
            people.append(person)
    yield f"due:{target.isoformat()}", people, {}


_TARGETS = {"event_before": _event_targets, "event_before_members": _event_targets, "membership_ending": _ending_targets, "period_due": _due_targets}


def run_rules(now: datetime | None = None) -> int:
    """Make and start the reminders that are due. Returns how many messages were started."""
    if not feature_enabled("message_reminders"):  # the package does not include automatic reminders (W14-R25); the rules and their data stay
        return 0
    zone = site_timezone()
    local_now = (now or datetime.now(timezone.utc)).astimezone(zone)
    started = 0
    for rule in MessageRule.query.filter_by(enabled=True).all():
        spec = TRIGGERS.get(rule.trigger)
        if spec is None or not trigger_available(spec) or local_now.hour < rule.send_hour:
            continue
        target_day = local_now.date() + timedelta(days=rule.offset_days)
        for key, people, context in _TARGETS[rule.trigger](rule, target_day):
            run = MessageRuleRun(rule_id=rule.id, target_key=key)
            db.session.add(run)
            try:
                db.session.flush()  # the unique pair is the guard against a second reminder
            except IntegrityError:
                db.session.rollback()
                continue
            if not people:
                db.session.commit()
                continue
            message = Message(kind="service", subject=rule.subject, body_html=rule.body_html, audience={"type": "rule", "params": {"rule_id": rule.id, "target": key}},
                              status="sending", source=f"rule:{rule.id}")
            db.session.add(message)
            db.session.flush()
            run.message_id = message.id
            db.session.commit()
            if queue_recipients(message, people, context) == 0:
                message.status = "sent"
                db.session.commit()
                continue
            start_sending(message.id)
            started += 1
    return started
