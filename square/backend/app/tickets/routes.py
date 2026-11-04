from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app.auth.optional import optional_admin_user
from app.events.models import Event
from app.extensions import db
from app.tickets.models import TicketType

tickets_bp = Blueprint("tickets", __name__, url_prefix="/api/tickets")


def _sold_count(ticket_type_id: int) -> int:
    from app.orders.models import Order, OrderItem

    stmt = (
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.ticket_type_id == ticket_type_id,
            Order.payment_status.in_(("pending", "paid")),
        )
    )
    return db.session.execute(stmt).scalar_one()


def _as_aware_utc(value: datetime | None) -> datetime | None:
    # SQLite (used in tests) drops tzinfo on round-trip for DateTime(timezone=True)
    # columns even though Postgres preserves it — values are always written as UTC, so a
    # naive value read back can be safely assumed to be UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ticket_type_status(ticket_type: TicketType, remaining: int | None) -> str:
    now = datetime.now(timezone.utc)
    sale_start = _as_aware_utc(ticket_type.sale_start)
    sale_end = _as_aware_utc(ticket_type.sale_end)
    event = db.session.get(Event, ticket_type.event_id)
    if sale_start and now < sale_start:
        return "upcoming"
    if event is not None and event.sales_not_open:
        return "upcoming"  # the whole event's sales have not opened yet
    if sale_end and now > sale_end:
        return "ended"
    if event is not None and event.sales_closed:
        return "ended"  # the whole event's sales cut-off has passed
    if remaining is not None and remaining <= 0:
        return "sold_out"
    return "on_sale"


def _serialize_ticket_type(ticket_type: TicketType) -> dict:
    remaining = None
    if ticket_type.capacity is not None:
        remaining = max(ticket_type.capacity - _sold_count(ticket_type.id), 0)
    return {
        "id": ticket_type.id,
        "name": ticket_type.name,
        "description": ticket_type.description,
        "price": ticket_type.price,
        "capacity": ticket_type.capacity,
        "remaining": remaining,
        "sale_start": ticket_type.sale_start.isoformat() if ticket_type.sale_start else None,
        "sale_end": ticket_type.sale_end.isoformat() if ticket_type.sale_end else None,
        "valid_on": ticket_type.valid_on.isoformat() if ticket_type.valid_on else None,
        "members_only": ticket_type.members_only,
        "age_category": ticket_type.age_category,
        "coupon_eligible": ticket_type.coupon_eligible,
        "status": _ticket_type_status(ticket_type, remaining),
    }


@tickets_bp.get("/types")
def list_ticket_types():
    event_id = request.args.get("event_id")
    if not event_id:
        return jsonify({"error": "event_id is required"}), 400
    try:
        event_id = int(event_id)
    except ValueError:
        return jsonify({"error": "event_id must be an integer"}), 400

    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    # An admin's own authenticated request can also list ticket types for a draft event — see
    # the matching note on app.events.routes.get_event.
    if not event.published and optional_admin_user() is None:
        return jsonify({"error": "Event not found"}), 404

    ticket_types = (
        TicketType.query.filter_by(event_id=event_id).order_by(TicketType.sort_order).all()
    )
    return jsonify({"items": [_serialize_ticket_type(t) for t in ticket_types]})
