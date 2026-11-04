"""One person's personal data in one JSON document (GDPR art. 15 / 20), for an admin to hand over.

Deliberately not gated by modules: data of a module that is switched off is still the person's
data and must be included (docs/LEGAL_TODO.md). Read-only; the route writes the audit entry.
"""

from datetime import datetime, timezone

from sqlalchemy import func, or_

from app.auth.models import User
from app.donations.models import Donation
from app.events.models import Event, EventTaskAssignment
from app.extensions import db
from app.members.models import Member
from app.messages.models import Message, MessageRecipient, MessageSuppression
from app.newsletter.models import Subscriber
from app.orders.models import Order


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _order(order: Order) -> dict:
    event = db.session.get(Event, order.event_id)
    return {
        "order_number": order.order_number,
        "event_title": event.title if event else None,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "customer_phone": order.customer_phone,
        "total_amount": order.total_amount,
        "coupon_code": order.coupon_code,
        "discount_amount": order.discount_amount,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "created_at": _iso(order.created_at),
        "tickets": [
            {"ticket_code": t.ticket_code, "status": t.status, "checked_in_at": _iso(t.checked_in_at)}
            for item in order.items
            for t in item.tickets
        ],
    }


def build_person_export(member: Member) -> dict:
    user = db.session.get(User, member.user_id) if member.user_id else None
    emails = {e.strip().lower() for e in (member.email, user.email if user else None) if e}

    match = Order.user_id == user.id if user else None
    if emails:
        by_email = func.lower(Order.customer_email).in_(emails)
        match = by_email if match is None else or_(match, by_email)
    orders = Order.query.filter(match).order_by(Order.created_at.desc()).all() if match is not None else []

    subscribers = (
        Subscriber.query.filter(func.lower(Subscriber.email).in_(emails)).all() if emails else []
    )
    tasks = EventTaskAssignment.query.filter_by(member_id=member.id).all()
    donation_match = Donation.user_id == user.id if user else None
    if emails:
        by_donor_email = func.lower(Donation.donor_email).in_(emails)
        donation_match = by_donor_email if donation_match is None else or_(donation_match, by_donor_email)
    donations = Donation.query.filter(donation_match).order_by(Donation.created_at.desc()).all() if donation_match is not None else []

    received = (
        db.session.query(Message.subject, Message.kind, Message.sent_at, MessageRecipient.status)
        .join(MessageRecipient, MessageRecipient.message_id == Message.id)
        .filter(func.lower(MessageRecipient.email).in_(emails))
        .order_by(Message.id.desc())
        .all()
        if emails
        else []
    )
    do_not_contact = MessageSuppression.query.filter(MessageSuppression.email.in_(emails)).count() > 0 if emails else False

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {"email": user.email, "phone": user.phone, "role": user.role} if user else None,
        "profile": {
            "name": member.name,
            "email": member.email,
            "phone": member.phone,
            "address": member.address,
            "photo_url": member.photo_url,
            "family_info": member.family_info,
            "created_at": _iso(member.created_at),
        },
        "family_members": [
            {"name": f.name, "relationship_type": f.relationship_type, "age": f.age}
            for f in member.family_members
        ],
        "memberships": [
            {
                "membership_type": m.membership_type,
                "status": m.status,
                "start_date": _iso(m.start_date),
                "end_date": _iso(m.end_date),
            }
            for m in member.memberships
        ],
        "orders": [_order(o) for o in orders],
        "newsletter": [
            {
                "email": s.email,
                "status": s.status,
                "consented_at": _iso(s.consented_at),
                "unsubscribed_at": _iso(s.unsubscribed_at),
            }
            for s in subscribers
        ],
        "donations": [
            {
                "reference": d.reference,
                "donor_name": d.donor_name,
                "donor_email": d.donor_email,
                "anonymous": d.anonymous,
                "message": d.message,
                "amount": d.amount,
                "currency": d.currency,
                "status": d.status,
                "created_at": _iso(d.created_at),
            }
            for d in donations
        ],
        "messages": {
            "do_not_contact": do_not_contact,
            "received": [{"subject": subject, "kind": kind, "sent_at": _iso(sent_at), "delivery": status} for subject, kind, sent_at, status in received],
        },
        "volunteer_tasks": [
            {"event_id": a.event_id, "category": a.category, "created_at": _iso(a.created_at)}
            for a in tasks
        ],
    }
