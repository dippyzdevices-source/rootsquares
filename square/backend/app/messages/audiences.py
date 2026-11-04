"""Audiences: who a message goes to. An audience is a rule worked out when the message is sent, never a stored list.

Every module that has people registers its audiences here; an audience of a module that is off does not exist (it is not offered and cannot be sent to).
A new module (classes for a language school, say) adds one entry and the Messages code does not change.

`params` describe what the admin fills in: {"name", "label", "type", "required"}; `type` is "event" (an event of the square), "membership_type",
"membership_status", or "emails" (pasted addresses). Recipients are de-duplicated by address, people without an address are left out.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import func, or_

from app.extensions import db
from app.modules import module_enabled

EMAIL_RE = re.compile(r"[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+")
MAX_CUSTOM_ADDRESSES = 500


@dataclass
class Recipient:
    email: str
    name: str = ""
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Audience:
    key: str
    label: str
    module: str | None
    description: str
    params: tuple[dict, ...]
    resolve: Callable[[dict], list[Recipient]]


def _clean(email: str | None) -> str:
    return (email or "").strip().lower()


def _erasing_addresses() -> set[str]:
    """Addresses of people whose erase is requested (or done): the audiences that work from orders or gifts must skip them too."""
    from app.auth.models import User
    from app.members.models import Member

    rows = (
        db.session.query(Member.email, User.email)
        .outerjoin(User, Member.user_id == User.id)
        .filter(or_(Member.erase_requested_at.isnot(None), Member.erased_at.isnot(None)))
        .all()
    )
    return {a for row in rows for a in (_clean(row[0]), _clean(row[1])) if a}


def _members(params: dict) -> list[Recipient]:
    from app.auth.models import User
    from app.members.models import Member
    from app.memberships.models import Membership

    query = db.session.query(Member, User.email).outerjoin(User, Member.user_id == User.id).filter(Member.erased_at.is_(None), Member.erase_requested_at.is_(None))
    status = params.get("membership_status")
    mtype = params.get("membership_type")
    if (status or mtype) and module_enabled("memberships"):
        query = query.join(Membership, Membership.member_id == Member.id)
        if status:
            query = query.filter(Membership.status == status)
        if mtype:
            query = query.filter(Membership.membership_type == mtype)
    out: dict[str, Recipient] = {}
    for member, user_email in query.order_by(Member.id).all():
        address = _clean(user_email or member.email)
        if address and address not in out:
            out[address] = Recipient(address, member.name)
    return list(out.values())


def _ticket_holders(params: dict) -> list[Recipient]:
    from app.orders.models import Order

    event_id = params.get("event_id")
    if not isinstance(event_id, int):
        return []
    out: dict[str, Recipient] = {}
    erasing = _erasing_addresses()
    for order in Order.query.filter_by(event_id=event_id, payment_status="paid").order_by(Order.id).all():
        address = _clean(order.customer_email)
        if address and address not in out and address not in erasing:
            out[address] = Recipient(address, order.customer_name)
    return list(out.values())


def _volunteers(params: dict) -> list[Recipient]:
    from app.auth.models import User
    from app.events.models import EventTaskAssignment
    from app.members.models import Member

    query = (
        db.session.query(Member, User.email)
        .join(EventTaskAssignment, EventTaskAssignment.member_id == Member.id)
        .outerjoin(User, Member.user_id == User.id)
        .filter(Member.erased_at.is_(None), Member.erase_requested_at.is_(None))
    )
    if isinstance(params.get("event_id"), int):
        query = query.filter(EventTaskAssignment.event_id == params["event_id"])
    out: dict[str, Recipient] = {}
    for member, user_email in query.order_by(Member.id).all():
        address = _clean(user_email or member.email)
        if address and address not in out:
            out[address] = Recipient(address, member.name)
    return list(out.values())


def _donors(params: dict) -> list[Recipient]:
    from app.donations.models import Donation

    out: dict[str, Recipient] = {}
    erasing = _erasing_addresses()
    for donation in Donation.query.filter_by(status="paid").order_by(Donation.id).all():
        address = _clean(donation.donor_email)
        if address and address not in out and address not in erasing:
            out[address] = Recipient(address, donation.donor_name)
    return list(out.values())


def _subscribers(params: dict) -> list[Recipient]:
    from app.newsletter.models import Subscriber

    return [Recipient(_clean(s.email)) for s in Subscriber.query.filter_by(status="subscribed").order_by(Subscriber.id).all() if _clean(s.email)]


def parse_addresses(raw: object) -> list[str]:
    """Pasted addresses (separated by spaces, commas, semicolons or lines), lower-cased and de-duplicated."""
    if not isinstance(raw, str):
        return []
    seen: dict[str, None] = {}
    for found in EMAIL_RE.findall(raw):
        seen.setdefault(found.lower(), None)
    return list(seen)


def _custom(params: dict) -> list[Recipient]:
    return [Recipient(a) for a in parse_addresses(params.get("emails"))[:MAX_CUSTOM_ADDRESSES]]


AUDIENCES: dict[str, Audience] = {
    a.key: a
    for a in (
        Audience("members", "Members and people", "members", "Everyone on the member list who has an e-mail address.",
                 ({"name": "membership_status", "label": "Membership status (optional)", "type": "membership_status", "required": False},
                  {"name": "membership_type", "label": "Membership type (optional)", "type": "membership_type", "required": False}), _members),
        Audience("ticket_holders", "Ticket holders of an event", "tickets", "People with a paid order for the event.",
                 ({"name": "event_id", "label": "Event", "type": "event", "required": True},), _ticket_holders),
        Audience("volunteers", "Volunteers", "volunteering", "Members with a task at an event (or at any event).",
                 ({"name": "event_id", "label": "Event (optional)", "type": "event", "required": False},), _volunteers),
        Audience("donors", "Donors", "donations", "People with a paid donation.", (), _donors),
        Audience("subscribers", "Newsletter subscribers", "newsletter", "People who subscribed on the website.", (), _subscribers),
        Audience("custom", "Addresses I type", None, "A list of e-mail addresses you paste in.",
                 ({"name": "emails", "label": "E-mail addresses", "type": "emails", "required": True},), _custom),
    )
}


def available_audiences() -> list[Audience]:
    return [a for a in AUDIENCES.values() if module_enabled(a.module)]


def validate_audience(audience: object) -> tuple[dict, str | None]:
    """Returns (clean audience, error). The audience must exist, its module must be on and its required parameters must be there."""
    if not isinstance(audience, dict) or audience.get("type") not in AUDIENCES:
        return {}, "Choose who the message goes to."
    spec = AUDIENCES[audience["type"]]
    if not module_enabled(spec.module):
        return {}, "That audience is not available."
    raw = audience.get("params") if isinstance(audience.get("params"), dict) else {}
    clean: dict = {}
    for param in spec.params:
        value = raw.get(param["name"])
        if value in (None, ""):
            if param["required"]:
                return {}, f"{param['label']} is required."
            continue
        if param["type"] == "event":
            from app.events.models import Event

            if not isinstance(value, int) or db.session.get(Event, value) is None:
                return {}, "That event does not exist."
        elif param["type"] == "emails":
            if not parse_addresses(value):
                return {}, "Add at least one valid e-mail address."
            value = " ".join(parse_addresses(value)[:MAX_CUSTOM_ADDRESSES])
        elif not isinstance(value, str) or len(value) > 50:
            return {}, f"{param['label']} is not valid."
        clean[param["name"]] = value
    return {"type": spec.key, "params": clean}, None


def resolve(audience: dict) -> list[Recipient]:
    spec = AUDIENCES.get(audience.get("type", ""))
    if spec is None or not module_enabled(spec.module):
        return []
    return spec.resolve(audience.get("params") or {})


def suppressed_count_hint() -> int:
    from app.messages.models import MessageSuppression

    return int(db.session.query(func.count(MessageSuppression.id)).scalar() or 0)
