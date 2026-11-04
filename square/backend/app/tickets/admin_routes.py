from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_, select

from app.audit.service import log_action
from app.email.service import EmailServiceNotConfiguredError, get_email_service
from app.email.templates import render_buyer_message_email
from app.auth.decorators import require_role
from app.auth.models import User
from app.events.models import Event
from app.common.query_params import csv_arg, csv_int_arg
from app.extensions import db
from app.imports.excel import write_xlsx
from app.members.service import member_name_for_user
from app.orders.models import Order, OrderItem
from app.tickets.models import Ticket, TicketType
from app.tickets.routes import _sold_count

admin_ticket_types_bp = Blueprint("admin_ticket_types", __name__, url_prefix="/api/admin")
admin_ticket_types_bp.before_request(require_role("admin"))

admin_tickets_bp = Blueprint("admin_tickets", __name__, url_prefix="/api/admin/tickets")
admin_tickets_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
VALID_TICKET_STATUSES = {"valid", "used", "void"}
VALID_AGE_CATEGORIES = {"adult", "child", "other"}


def _user_email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user else None


def _serialize_ticket_type_admin(ticket_type: TicketType) -> dict:
    return {
        "id": ticket_type.id,
        "event_id": ticket_type.event_id,
        "name": ticket_type.name,
        "description": ticket_type.description,
        "price": ticket_type.price,
        "capacity": ticket_type.capacity,
        "sold": _sold_count(ticket_type.id),
        "sale_start": ticket_type.sale_start.isoformat() if ticket_type.sale_start else None,
        "sale_end": ticket_type.sale_end.isoformat() if ticket_type.sale_end else None,
        "valid_on": ticket_type.valid_on.isoformat() if ticket_type.valid_on else None,
        "members_only": ticket_type.members_only,
        "age_category": ticket_type.age_category,
        "coupon_eligible": ticket_type.coupon_eligible,
        "sort_order": ticket_type.sort_order,
        "created_by_email": _user_email(ticket_type.created_by),
        "updated_by_email": _user_email(ticket_type.updated_by),
    }


def _event_days(event: Event | None) -> list[date]:
    """Calendar days (Oslo time) a multi-day event runs on; empty for a single-day event."""
    if event is None or event.end_datetime is None:
        return []
    oslo = ZoneInfo("Europe/Oslo")

    def local_day(value: datetime) -> date:
        value = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
        return value.astimezone(oslo).date()

    first, last = local_day(event.start_datetime), local_day(event.end_datetime)
    if last <= first:
        return []
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _validate_ticket_type_payload(
    data: dict, existing: TicketType | None, event: Event | None = None
) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        if not data.get("name"):
            errors["name"] = "This field is required."
        if data.get("price") is None:
            errors["price"] = "This field is required."
        if "valid_on" not in data and _event_days(event):
            errors["valid_on"] = "Choose the day this ticket is valid on, or All days."
        if not data.get("age_category"):
            errors["age_category"] = "Choose an age group."

    if "name" in data:
        value = data["name"]
        if not isinstance(value, str) or not value.strip():
            errors["name"] = "Must be a non-empty string."
        elif len(value) > 100:
            errors["name"] = "Must be at most 100 characters."
        else:
            cleaned["name"] = value.strip()

    if "price" in data:
        value = data["price"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["price"] = "Must be a non-negative integer (minor units)."
        else:
            cleaned["price"] = value

    if "description" in data:
        value = data["description"]
        if value is None:
            cleaned["description"] = None
        elif not isinstance(value, str):
            errors["description"] = "Must be a string or null."
        elif len(value) > 2000:
            errors["description"] = "Must be at most 2000 characters."
        else:
            cleaned["description"] = value.strip() or None

    if "capacity" in data:
        value = data["capacity"]
        if value is None:
            cleaned["capacity"] = None
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["capacity"] = "Must be a non-negative integer or null."
        else:
            cleaned["capacity"] = value

    for field in ("sale_start", "sale_end"):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
            continue
        try:
            cleaned[field] = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            errors[field] = "Must be a valid ISO 8601 datetime."

    if "valid_on" in data:
        value = data["valid_on"]
        if value in (None, ""):
            cleaned["valid_on"] = None
        else:
            try:
                cleaned["valid_on"] = date.fromisoformat(value)
            except (ValueError, TypeError):
                errors["valid_on"] = "Must be a valid date (YYYY-MM-DD) or null."
            else:
                days = _event_days(event)
                if days and cleaned["valid_on"] not in days:
                    errors["valid_on"] = "Must be one of the event's days."

    if "members_only" in data:
        value = data["members_only"]
        if not isinstance(value, bool):
            errors["members_only"] = "Must be a boolean."
        else:
            cleaned["members_only"] = value

    if "age_category" in data:
        value = data["age_category"]
        if value not in VALID_AGE_CATEGORIES:
            errors["age_category"] = f"Must be one of {sorted(VALID_AGE_CATEGORIES)}."
        else:
            cleaned["age_category"] = value

    if "coupon_eligible" in data:
        value = data["coupon_eligible"]
        if not isinstance(value, bool):
            errors["coupon_eligible"] = "Must be a boolean."
        else:
            cleaned["coupon_eligible"] = value

    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["sort_order"] = "Must be an integer."
        else:
            cleaned["sort_order"] = value

    return cleaned, errors


@admin_ticket_types_bp.get("/events/<int:event_id>/ticket-types")
def admin_list_ticket_types(event_id: int):
    ticket_types = (
        TicketType.query.filter_by(event_id=event_id).order_by(TicketType.sort_order).all()
    )
    return jsonify({"items": [_serialize_ticket_type_admin(t) for t in ticket_types]})


@admin_ticket_types_bp.post("/events/<int:event_id>/ticket-types")
def admin_create_ticket_type(event_id: int):
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_ticket_type_payload(data, existing=None, event=db.session.get(Event, event_id))
    if errors:
        return jsonify({"errors": errors}), 400

    ticket_type = TicketType(
        event_id=event_id,
        name=cleaned["name"],
        description=cleaned.get("description"),
        price=cleaned["price"],
        capacity=cleaned.get("capacity"),
        sale_start=cleaned.get("sale_start"),
        sale_end=cleaned.get("sale_end"),
        valid_on=cleaned.get("valid_on"),
        members_only=cleaned.get("members_only", False),
        age_category=cleaned.get("age_category", "other"),
        coupon_eligible=cleaned.get("coupon_eligible", True),
        sort_order=cleaned.get("sort_order", 0),
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(ticket_type)
    db.session.commit()

    return jsonify(_serialize_ticket_type_admin(ticket_type)), 201


@admin_ticket_types_bp.patch("/ticket-types/<int:ticket_type_id>")
def admin_update_ticket_type(ticket_type_id: int):
    ticket_type = db.session.get(TicketType, ticket_type_id)
    if ticket_type is None:
        return jsonify({"error": "Ticket type not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_ticket_type_payload(data, existing=ticket_type, event=db.session.get(Event, ticket_type.event_id))
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(ticket_type, field, value)
    ticket_type.updated_by = g.current_user.id

    db.session.commit()
    return jsonify(_serialize_ticket_type_admin(ticket_type))


@admin_ticket_types_bp.delete("/ticket-types/<int:ticket_type_id>")
def admin_delete_ticket_type(ticket_type_id: int):
    ticket_type = db.session.get(TicketType, ticket_type_id)
    if ticket_type is None:
        return jsonify({"error": "Ticket type not found"}), 404

    ticket_type_name = ticket_type.name
    event = db.session.get(Event, ticket_type.event_id)
    event_title = event.title if event else "an unknown event"

    db.session.delete(ticket_type)
    db.session.commit()

    log_action(
        g.current_user,
        "ticket_type_deleted",
        f'Deleted ticket type "{ticket_type_name}" for "{event_title}"',
        target_type="ticket_type",
        target_id=ticket_type_id,
    )

    return "", 204


def _serialize_ticket_admin(ticket: Ticket) -> dict:
    order = ticket.order_item.order
    checked_in_by = (
        db.session.get(User, ticket.checked_in_by_user_id)
        if ticket.checked_in_by_user_id
        else None
    )
    return {
        "id": ticket.id,
        "order_id": order.id,
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "ticket_type": ticket.order_item.ticket_type.name if ticket.order_item.ticket_type else None,
        "event_id": order.event_id,
        "issued_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "checked_in_at": ticket.checked_in_at.isoformat() if ticket.checked_in_at else None,
        "checked_in_by": checked_in_by.email if checked_in_by else None,
        "checked_in_by_name": member_name_for_user(ticket.checked_in_by_user_id),
    }


def _tickets_query_with_search_and_filters():
    """Shared by the list and export routes — a join over Ticket -> OrderItem -> Order so
    `event_id`/`status`/`q` (ticket code, customer name, or email) can all filter in one query.
    """
    stmt = select(Ticket).join(OrderItem, Ticket.order_item_id == OrderItem.id).join(
        Order, OrderItem.order_id == Order.id
    )

    # Default ordering is by id (newest ticket first). `sort=checked_in_at_desc` orders by
    # when a ticket was actually scanned instead — used by the admin Check-in overview's
    # "Last scans" list, where recency of the scan (not of ticket creation) is what matters.
    if request.args.get("sort") == "checked_in_at_desc":
        stmt = stmt.order_by(Ticket.checked_in_at.desc())
    else:
        stmt = stmt.order_by(Ticket.id.desc())

    event_ids = csv_int_arg("event_id")
    if event_ids:
        stmt = stmt.where(Order.event_id.in_(event_ids))

    statuses = csv_arg("status")
    if statuses:
        stmt = stmt.where(Ticket.status.in_(statuses))

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Ticket.ticket_code.ilike(like),
                Order.customer_name.ilike(like),
                Order.customer_email.ilike(like),
            )
        )

    return stmt


MAX_BUYER_RECIPIENTS = 250  # the message is sent while the admin waits, one e-mail per buyer


def _buyer_emails(event_id: int) -> list[str]:
    """The distinct e-mail addresses (lower case) of everyone with a PAID order for the event, in the order they first bought."""
    rows = db.session.execute(
        select(Order.customer_email).where(Order.event_id == event_id, Order.payment_status == "paid").order_by(Order.created_at.asc(), Order.id.asc())
    ).scalars()
    seen: dict[str, None] = {}
    for email in rows:
        if email and email.strip():
            seen.setdefault(email.strip().lower(), None)
    return list(seen)


@admin_tickets_bp.get("/buyers/count")
def admin_count_buyers():
    """How many people a message to the buyers of an event would reach (shown before sending)."""
    try:
        event_id = int(request.args.get("event_id", ""))
    except ValueError:
        return jsonify({"error": "event_id is required"}), 400
    if db.session.get(Event, event_id) is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify({"count": len(_buyer_emails(event_id)), "max": MAX_BUYER_RECIPIENTS})


@admin_tickets_bp.post("/message-buyers")
def admin_message_buyers():
    """E-mail everyone who bought tickets for an event (doors open at 7, a change of room, ...). One e-mail per buyer, so addresses are never shown to each
    other. Needs the sending e-mail to be set up; answers 503 before sending anything when it is not."""
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    event = db.session.get(Event, data.get("event_id")) if isinstance(data.get("event_id"), int) else None
    if event is None:
        errors["event_id"] = "Choose an event."
    subject = data.get("subject")
    message = data.get("message")
    if not isinstance(subject, str) or not subject.strip():
        errors["subject"] = "This field is required."
    elif len(subject.strip()) > 150:
        errors["subject"] = "Must be at most 150 characters."
    if not isinstance(message, str) or not message.strip():
        errors["message"] = "This field is required."
    elif len(message) > 5000:
        errors["message"] = "Must be at most 5000 characters."
    if errors:
        return jsonify({"errors": errors}), 400
    recipients = _buyer_emails(event.id)
    if not recipients:
        return jsonify({"error": "Nobody has bought a ticket for this event yet.", "code": "no_buyers"}), 409
    if len(recipients) > MAX_BUYER_RECIPIENTS:
        return jsonify({"error": f"More than {MAX_BUYER_RECIPIENTS} buyers: this message cannot be sent in one go.", "code": "too_many_buyers"}), 409
    html_body, text_body, attachments = render_buyer_message_email(subject=subject.strip(), message=message.strip(), event_title=event.title)
    service = get_email_service()
    sent = failed = 0
    for address in recipients:
        try:
            service.send_email(to=address, subject=subject.strip(), html=html_body, text=text_body, attachments=attachments)
            sent += 1
        except EmailServiceNotConfiguredError:
            if sent == 0 and failed == 0:
                return jsonify({"error": "Sending e-mail is not set up for this site yet.", "code": "email_not_configured"}), 503
            failed += 1
        except Exception:  # one bad address or a provider hiccup must not stop the rest
            failed += 1
    log_action(g.current_user, "buyers_messaged", f"Messaged the buyers of event #{event.id} ({sent} sent, {failed} failed)", target_type="event", target_id=event.id)
    return jsonify({"sent": sent, "failed": failed})


@admin_tickets_bp.get("")
def admin_list_tickets():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    if any(s not in VALID_TICKET_STATUSES for s in csv_arg("status")):
        return jsonify({"error": f"status must be one of {sorted(VALID_TICKET_STATUSES)}"}), 400

    stmt = _tickets_query_with_search_and_filters()
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    event_titles = {e.id: e.title for e in Event.query.all()}
    items = []
    for ticket in pagination.items:
        serialized = _serialize_ticket_admin(ticket)
        serialized["event_title"] = event_titles.get(serialized["event_id"])
        items.append(serialized)

    return jsonify(
        {
            "items": items,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_tickets_bp.get("/export")
def admin_export_tickets():
    if any(s not in VALID_TICKET_STATUSES for s in csv_arg("status")):
        return jsonify({"error": f"status must be one of {sorted(VALID_TICKET_STATUSES)}"}), 400

    tickets = db.session.execute(_tickets_query_with_search_and_filters()).scalars().all()
    event_titles = {e.id: e.title for e in Event.query.all()}

    headers = [
        "Ticket code", "Customer name", "Customer email", "Event", "Ticket type",
        "Status", "Issued at", "Checked in at", "Checked in by",
    ]
    rows = []
    for ticket in tickets:
        serialized = _serialize_ticket_admin(ticket)
        rows.append(
            [
                serialized["ticket_code"],
                serialized["customer_name"],
                serialized["customer_email"],
                event_titles.get(serialized["event_id"]),
                serialized["ticket_type"],
                serialized["status"],
                serialized["issued_at"],
                serialized["checked_in_at"],
                serialized["checked_in_by"],
            ]
        )

    data = write_xlsx(headers, rows)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tickets.xlsx"},
    )
