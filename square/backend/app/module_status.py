"""Whether a module holds data and what is still in progress in it (rootsquares W8-R27, docs/reference/optional-modules.md section 9c and ADR 038; not in bca-oslo).

The owner switches modules on the platform. Before switching one off the platform asks this server two things per module: does it hold any data (yes or no)
and is anything still in progress (plain sentences the owner reads and confirms). NO NUMBERS and no content leave the square: a number of rows can say
something about a person. The square app keeps the knowledge of its own tables; the platform never reads the square's database for this.

`GET /api/internal/modules/status` answers only a caller that sends the shared key (`PLATFORM_INTERNAL_KEY`, header `X-Internal-Key`); without a
configured key it does not exist (404). It is meant for the platform's server, never for browsers.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.modules import MODULE_KEYS, module_enabled

internal_bp = Blueprint("internal", __name__, url_prefix="/api/internal")


def _count(query: Any) -> int:
    return int(query.count())


Status = tuple[int, list[str]]  # (how many rows the module holds: only used here to say yes or no, never sent; pending: [sentence])


def _events() -> Status:
    from app.events.models import Event

    now = datetime.now(timezone.utc)
    upcoming = _count(Event.query.filter(Event.published.is_(True), Event.start_datetime >= now))
    return _count(Event.query), (["Upcoming events are published and will no longer be shown."] if upcoming else [])


def _tickets() -> Status:
    from app.orders.models import Order

    waiting = _count(Order.query.filter(Order.payment_status.in_(["pending", "pending_verification", "initiated"])))
    return _count(Order.query), (["Orders are waiting for payment or approval."] if waiting else [])


def _payments() -> Status:
    from app.payments.models import Payment

    waiting = _count(Payment.query.filter(Payment.status.in_(["pending", "pending_verification", "initiated"])))
    return _count(Payment.query), (["Payments are waiting for confirmation."] if waiting else [])


def _coupons() -> Status:
    from app.coupons.models import Coupon

    return _count(Coupon.query), []


def _checkin() -> Status:
    from app.tickets.models import Ticket

    return _count(Ticket.query.filter(Ticket.status == "used")), []


def _members() -> Status:
    from app.members.models import Member

    return _count(Member.query), []


def _memberships() -> Status:
    from app.memberships.models import Membership, MembershipPeriod

    requests = _count(Membership.query.filter(Membership.status == "pending"))
    unpaid = _count(MembershipPeriod.query.filter(MembershipPeriod.status == "unpaid"))
    pending = []
    if requests:
        pending.append("Membership requests are waiting for review or payment.")
    if unpaid:
        pending.append("Membership periods are unpaid and will not be followed up.")
    return _count(Membership.query), pending


def _volunteering() -> Status:
    from app.events.models import Event, EventTaskAssignment

    now = datetime.now(timezone.utc)
    upcoming = _count(EventTaskAssignment.query.join(Event, EventTaskAssignment.event_id == Event.id).filter(Event.start_datetime >= now))
    return _count(EventTaskAssignment.query), (["Volunteer assignments for upcoming events will no longer be shown to the volunteers."] if upcoming else [])


def _accounting() -> Status:
    from app.accounting.models import Expense

    return _count(Expense.query), []


def _gallery() -> Status:
    from app.gallery.models import Album, Media

    return _count(Album.query) + _count(Media.query), []


def _news() -> Status:
    from app.news.models import News

    return _count(News.query), []


def _magazines() -> Status:
    from app.magazines.models import Magazine

    return _count(Magazine.query), []


def _newsletter() -> Status:
    # newsletters are Messages now (W14-R20): what is scheduled or sending is reported by the Messages module
    from app.newsletter.models import NewsletterIssue, Subscriber

    return _count(Subscriber.query) + _count(NewsletterIssue.query), []


def _testimonials() -> Status:
    from app.testimonials.models import Testimonial

    waiting = _count(Testimonial.query.filter(Testimonial.status == "pending"))
    return _count(Testimonial.query), (["Testimonials are waiting for approval."] if waiting else [])


def _sponsors() -> Status:
    from app.sponsors.models import Sponsor

    return _count(Sponsor.query), []


def _committee() -> Status:
    from app.committee.models import CommitteeMember

    return _count(CommitteeMember.query), []


def _founders() -> Status:
    from app.founders.models import Founder

    return _count(Founder.query), []


def _donations() -> Status:
    from app.donations.models import Donation

    waiting = _count(Donation.query.filter(Donation.status.in_(["pending", "pending_verification"])))
    return _count(Donation.query), (["Donations are waiting for confirmation."] if waiting else [])


def _messages() -> Status:
    from app.messages.models import Message

    waiting = _count(Message.query.filter(Message.status.in_(["scheduled", "sending"])))
    return _count(Message.query), (["Messages are scheduled or being sent."] if waiting else [])


# One function per module; a module that has nothing in progress simply returns an empty pending list. Keep in step with MODULE_KEYS (a test checks it).
MODULE_STATUS: dict[str, Callable[[], Status]] = {
    "events": _events,
    "payments": _payments,
    "tickets": _tickets,
    "coupons": _coupons,
    "checkin": _checkin,
    "members": _members,
    "memberships": _memberships,
    "volunteering": _volunteering,
    "accounting": _accounting,
    "gallery": _gallery,
    "news": _news,
    "magazines": _magazines,
    "newsletter": _newsletter,
    "testimonials": _testimonials,
    "sponsors": _sponsors,
    "committee": _committee,
    "founders": _founders,
    "donations": _donations,
    "messages": _messages,
}


def module_status() -> list[dict]:
    """Per module: `holds_data` (yes or no, never a number) and `pending` ([sentence]). One failing module is left out, never the others."""
    items = []
    for key in MODULE_KEYS:
        try:
            rows, pending = MODULE_STATUS[key]()
        except Exception:  # noqa: BLE001 - a status that cannot be counted must not break the owner's screen
            current_app.logger.exception("module status failed for %s", key)
            continue
        items.append({"key": key, "holds_data": rows > 0, "pending": pending, "on": module_enabled(key)})
    return items


def _key_ok() -> bool:
    expected = str(current_app.config.get("PLATFORM_INTERNAL_KEY") or "")
    if not expected:
        return False
    return hmac.compare_digest(request.headers.get("X-Internal-Key", "").encode(), expected.encode())


@internal_bp.get("/modules/status")
def modules_status():
    if not _key_ok():
        return jsonify({"error": "Not found"}), 404  # same answer for a missing and a wrong key: nothing tells that the address exists
    tenant = g.get("tenant")
    if tenant is not None and tenant.sleeping:
        return jsonify({"items": []})  # asleep: its project may be paused, nothing is read
    return jsonify({"items": module_status()})


@internal_bp.get("/health")
def square_health():
    """The square's health for its owner (W10-R19): states and sentences only, see app/health_report.py."""
    if not _key_ok():
        return jsonify({"error": "Not found"}), 404
    from app.health_report import health_report

    return jsonify(health_report())


@internal_bp.get("/sleep-snapshot")
def sleep_snapshot():
    """The PUBLIC contact details (the ones the Contact page shows), read just before the platform puts the square to sleep so the back-soon page can show them
    while the square's project is paused (W10-R44, ADR 038 addition). Nothing else leaves the square."""
    if not _key_ok():
        return jsonify({"error": "Not found"}), 404
    from app.settings.models import get_site_settings

    settings = get_site_settings()
    return jsonify({"contact_email": settings.contact_email or "", "contact_phone": settings.contact_phone or "", "contact_address": settings.contact_address or ""})
