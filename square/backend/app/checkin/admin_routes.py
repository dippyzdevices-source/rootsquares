"""Ticket check-in — scanning and validation, admin or volunteer.

Every scan outcome below returns HTTP 200: invalid/not_assigned/already_used/voided/valid are
all valid business outcomes, not error conditions (see PRD §22's three-way flow, extended with
`not_assigned`, and later `voided` for a ticket on a cancelled order — app/orders/admin_routes.py's
admin_cancel_order). The URL prefix says "admin" for consistency with every other protected route
in this app, but the actual role check below admits volunteers too — door duty shouldn't
require full admin access.

There is deliberately no event-selection step before scanning (removed 2026-09-15 per explicit
user instruction — a volunteer at the door scans a code and everything about it, including
which event it belongs to, is read straight off the ticket itself). A volunteer's own
event-assignment scoping (`EventVolunteer`, still managed from `/admin/volunteers`) is now
checked *after* the ticket is looked up, against the ticket's real event, instead of being
enforced up front against a pre-selected event — this is what `not_assigned` reports.
"""

from datetime import date, datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import exists

from app.auth.decorators import require_role
from app.auth.models import User
from app.checkin.models import EventVolunteer
from app.events.models import Event
from app.extensions import db
from app.members.service import member_name_for_user
from app.orders.models import Order, OrderItem
from app.tickets.models import Ticket

checkin_bp = Blueprint("checkin", __name__, url_prefix="/api/admin/checkin")
checkin_bp.before_request(require_role("admin", "volunteer"))


def _volunteer_can_access_event(user: User, event_id: int) -> bool:
    if user.role == "admin":
        return True
    return db.session.query(
        exists().where(EventVolunteer.event_id == event_id, EventVolunteer.user_id == user.id)
    ).scalar()


def _ticket_display(ticket: Ticket, event_title: str | None) -> dict:
    order = ticket.order_item.order
    return {
        "customer_name": order.customer_name,
        "ticket_type": ticket.order_item.ticket_type.name,
        "event_title": event_title,
    }


def _event_date_window(event: Event) -> tuple[date, date]:
    """The inclusive UTC calendar-day range a ticket may be checked in on.

    `end_datetime` is optional (single-day events) — falls back to the start date. Uses UTC
    calendar dates, matching this codebase's existing sale_start/sale_end window convention
    (app/tickets/routes.py) rather than converting to Oslo local time.
    """
    start = event.start_datetime.date()
    end = event.end_datetime.date() if event.end_datetime else start
    return start, end


@checkin_bp.post("/scan")
def scan_ticket():
    data = request.get_json(silent=True) or {}
    ticket_code = (data.get("ticket_code") or "").strip()

    ticket = Ticket.query.filter_by(ticket_code=ticket_code).first() if ticket_code else None
    if ticket is None:
        return jsonify({"result": "invalid"})

    order = ticket.order_item.order
    event = db.session.get(Event, order.event_id)
    event_title = event.title if event else None

    if not _volunteer_can_access_event(g.current_user, order.event_id):
        return jsonify({"result": "not_assigned", "event_title": event_title})

    if ticket.status == "void":
        return jsonify({"result": "voided", **_ticket_display(ticket, event_title)})

    if ticket.status == "used":
        checked_in_by = (
            db.session.get(User, ticket.checked_in_by_user_id)
            if ticket.checked_in_by_user_id
            else None
        )
        return jsonify(
            {
                "result": "already_used",
                "checked_in_at": ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
                "checked_in_by": checked_in_by.email if checked_in_by else None,
                "checked_in_by_name": member_name_for_user(ticket.checked_in_by_user_id),
                **_ticket_display(ticket, event_title),
            }
        )

    if event is not None:
        event_start_date, event_end_date = _event_date_window(event)
        today = datetime.now(timezone.utc).date()
        if today < event_start_date:
            return jsonify(
                {
                    "result": "pre_event",
                    "event_start_date": event_start_date.isoformat(),
                    **_ticket_display(ticket, event_title),
                }
            )
        if today > event_end_date:
            return jsonify(
                {
                    "result": "post_event",
                    "event_end_date": event_end_date.isoformat(),
                    **_ticket_display(ticket, event_title),
                }
            )

    ticket.status = "used"
    ticket.checked_in_at = datetime.now(timezone.utc)
    ticket.checked_in_by_user_id = g.current_user.id
    db.session.commit()

    return jsonify({"result": "valid", **_ticket_display(ticket, event_title)})


@checkin_bp.get("/summary")
def checkin_summary():
    """Live running count across every event the caller may check people into — every
    published event for an admin, only assigned ones for a volunteer — since there is no
    longer a single pre-selected event to scope this to."""
    base = (
        db.session.query(Ticket)
        .join(OrderItem, Ticket.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
    )
    if g.current_user.role != "admin":
        base = base.join(
            EventVolunteer,
            (EventVolunteer.event_id == Order.event_id)
            & (EventVolunteer.user_id == g.current_user.id),
        )
    # A voided ticket (cancelled order — see admin_cancel_order) will never be checked in, so it's
    # excluded from the expected-attendance total rather than silently dragging the rate down.
    base = base.filter(Ticket.status != "void")
    total = base.count()
    checked_in = base.filter(Ticket.status == "used").count()

    return jsonify({"total_tickets": total, "checked_in_count": checked_in})
