from datetime import datetime, timezone
import uuid

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from app.common.site import site_currency
from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.accounting.models import EventContribution, Expense
from app.accounting.report_pdf import build_event_report_pdf
from app.accounting.receipts import ReceiptValidationError, validate_receipt
from app.coupons.models import Coupon
from app.modules import module_enabled
from app.events.models import Event
from app.common.query_params import csv_arg, csv_int_arg
from app.extensions import db
from app.lookups.service import active_values, label_for
from app.imports.excel import write_xlsx, write_xlsx_sheets
from app.members.service import member_name_for_user
from app.orders.models import Order, OrderItem
from app.payments.fees import processing_fee_for
from app.payments.models import Payment
from app.storage.service import get_private_storage
from app.tickets.models import Ticket, TicketType

admin_accounting_bp = Blueprint(
    "admin_accounting", __name__, url_prefix="/api/admin/accounting"
)
admin_accounting_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
REQUIRED_EXPENSE_FIELDS = ("date", "description", "category", "amount")


def _serialize_expense(expense: Expense) -> dict:
    creator = db.session.get(User, expense.created_by) if expense.created_by else None
    return {
        "id": expense.id,
        "event_id": expense.event_id,
        "date": expense.date.isoformat(),
        "description": expense.description,
        "category": expense.category,
        "amount": expense.amount,
        "vendor": expense.vendor,
        "notes": expense.notes,
        "receipt_key": expense.receipt_key,
        "receipt_url": get_private_storage().url_for(expense.receipt_key) if expense.receipt_key else None,
        "created_by": creator.email if creator else None,
        "created_at": expense.created_at.isoformat(),
        "updated_at": expense.updated_at.isoformat(),
    }


def _latest_payment_by_order(orders: list[Order]) -> dict[int, Payment]:
    """Each order's most recent payment, fetched in one query instead of one per order (the database is remote,
    so a query per row made the Collections table take seconds)."""
    ids = [o.id for o in orders]
    if not ids:
        return {}
    payments = db.session.scalars(
        select(Payment).where(Payment.order_id.in_(ids)).order_by(Payment.created_at.asc(), Payment.id.asc())
    ).all()
    return {p.order_id: p for p in payments}  # a later payment replaces an earlier one


def _ticket_type_day_key(ticket_type: TicketType | None) -> tuple:
    """Sort key used everywhere ticket lines are listed: by day (undated last), then the admin's own order."""
    if ticket_type is None:
        return (True, 0, 0, "")
    return (ticket_type.valid_on is None, ticket_type.valid_on or 0, ticket_type.sort_order, ticket_type.name)


def _ticket_line(item: OrderItem) -> str:
    """e.g. "2 × Adult · Fri 16 Oct" (the day only for a ticket type that is valid on one)."""
    tt = item.ticket_type
    line = f"{item.quantity} × {tt.name if tt else 'Ticket'}"
    if tt is not None and tt.valid_on:
        line += f" · {tt.valid_on.strftime('%a %d %b')}"
    return line


def _serialize_order_collection(order: Order, payment: Payment | None) -> dict:
    return {
        "id": order.id,
        "date": order.created_at.isoformat(),
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        # What was bought, one line per ticket type, e.g. ["2 × Adult", "1 × Child"]. A list, because ticket
        # names themselves contain commas, so a joined string would be ambiguous.
        "tickets": [_ticket_line(item) for item in sorted(order.items, key=lambda i: _ticket_type_day_key(i.ticket_type))],
        "payment_method": payment.provider if payment else None,
        # A free order (100% coupon) has no payment record; the coupon is how it was "paid".
        "coupon_code": order.coupon_code,
        "amount": order.total_amount,
        "payment_status": order.payment_status,
    }


def _validate_expense_payload(data: dict, *, is_create: bool, current_category: str | None = None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if is_create:
        for field in REQUIRED_EXPENSE_FIELDS:
            if data.get(field) in (None, ""):
                errors[field] = "This field is required."

    if "date" in data:
        raw = data["date"]
        try:
            cleaned["date"] = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
            if cleaned["date"] is None:
                errors["date"] = "This field is required."
        except (TypeError, ValueError):
            errors["date"] = "Must be a valid date (YYYY-MM-DD)."

    if "description" in data:
        value = data["description"]
        if not isinstance(value, str) or not value.strip():
            errors["description"] = "This field is required."
        elif len(value) > 300:
            errors["description"] = "Must be at most 300 characters."
        else:
            cleaned["description"] = value.strip()

    if "category" in data:
        value = data["category"]
        if value not in active_values("expense_category") and value != current_category:
            errors["category"] = f"Must be one of {sorted(active_values('expense_category'))}."
        else:
            cleaned["category"] = value

    if "amount" in data:
        value = data["amount"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            errors["amount"] = "Must be a number greater than zero."
        else:
            cleaned["amount"] = int(value)

    for field, max_length in (("vendor", 200),):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
            continue
        if not isinstance(value, str):
            errors[field] = "Must be a string or null."
            continue
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value.strip() or None

    if "notes" in data:
        value = data["notes"]
        if value is None:
            cleaned["notes"] = None
        elif not isinstance(value, str):
            errors["notes"] = "Must be a string or null."
        else:
            cleaned["notes"] = value.strip() or None

    return cleaned, errors


@admin_accounting_bp.get("/events/<int:event_id>")
def admin_accounting_event_summary(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(_build_event_summary(event))


def _fees_by_provider(event_id: int) -> list[dict]:
    """Per payment provider: the convenience fees customers paid on top (counted in Collection) and
    the estimated processing fees the provider took (counted in Expenses). Processing fees are kept
    on refunded payments too (the provider normally keeps its fee); convenience fees only count
    while the order is paid."""
    rows = (
        db.session.query(Payment, Order.payment_status)
        .join(Order, Payment.order_id == Order.id)
        .filter(
            Order.event_id == event_id,
            Payment.payment_type == "event_ticket",
            Payment.status.in_(("paid", "refunded", "partially_refunded")),
        )
        .all()
    )
    by_provider: dict[str, dict] = {}
    for payment, order_status in rows:
        entry = by_provider.setdefault(payment.provider, {"provider": payment.provider, "convenience": 0, "processing": 0})
        if order_status == "paid":
            entry["convenience"] += payment.surcharge_amount or 0
        # Payments paid before fees were recorded have no snapshot: estimate with today's rates.
        entry["processing"] += (
            payment.processing_fee_amount
            if payment.processing_fee_amount is not None
            else processing_fee_for(payment.provider, payment.amount)
        )
    # Online donations absorb the fee: no convenience fee is charged, but the provider still takes its
    # processing fee, which is an expense. `processing_donations` is the part that came from donations
    # (the Tickets by Channels card shows only the ticket part as that channel's commission).
    donation_payments = (
        db.session.query(Payment)
        .join(EventContribution, EventContribution.payment_id == Payment.id)
        .filter(
            EventContribution.event_id == event_id,
            Payment.payment_type == "event_donation",
            Payment.status.in_(("paid", "refunded", "partially_refunded")),
        )
        .all()
    )
    for payment in donation_payments:
        entry = by_provider.setdefault(
            payment.provider, {"provider": payment.provider, "convenience": 0, "processing": 0}
        )
        fee = (
            payment.processing_fee_amount
            if payment.processing_fee_amount is not None
            else processing_fee_for(payment.provider, payment.amount)
        )
        entry["processing"] += fee
        entry["processing_donations"] = entry.get("processing_donations", 0) + fee
    return sorted(
        (e for e in by_provider.values() if e["convenience"] or e["processing"]),
        key=lambda e: e["provider"],
    )


def _build_event_summary(event: Event) -> dict:
    """Everything the accounting page's summary cards show, shared with the PDF report."""
    event_id = event.id
    collection_total = (
        db.session.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.event_id == event_id, Order.payment_status == "paid")
        .scalar()
    )
    recorded_expenses_total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.event_id == event_id)
        .scalar()
    )
    # Donations and sponsorships received (admin-recorded or via the donate form) count as money in.
    contribution_rows = dict(
        db.session.query(EventContribution.kind, func.coalesce(func.sum(EventContribution.amount), 0))
        .filter(EventContribution.event_id == event_id, EventContribution.status == "paid")
        .group_by(EventContribution.kind)
        .all()
    )
    donations_total = int(contribution_rows.get("donation", 0))
    pending_contributions = (
        db.session.query(func.count(EventContribution.id))
        .filter(EventContribution.event_id == event_id, EventContribution.status == "pending")
        .scalar()
    )
    sponsorships_total = int(contribution_rows.get("sponsorship", 0))
    collection_total += donations_total + sponsorships_total
    # Collection = everything customers paid in (order totals + convenience fees); Expenses also
    # carry the providers' processing fees, so Net matches what actually lands in the bank.
    fees_by_provider = _fees_by_provider(event_id)
    collection_total += sum(f["convenience"] for f in fees_by_provider)
    processing_fees_total = sum(f["processing"] for f in fees_by_provider)
    expenses_total = recorded_expenses_total + processing_fees_total

    tickets_query = (
        db.session.query(Ticket)
        .join(OrderItem, Ticket.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.event_id == event_id, Order.payment_status == "paid")
    )
    tickets_sold = tickets_query.count()
    # Check-in: voided tickets (cancelled orders) can no longer be scanned, so they are not "expected".
    tickets_expected = tickets_query.filter(Ticket.status != "void").count()
    tickets_checked_in = tickets_query.filter(Ticket.status == "used").count()

    tickets_by_type_rows = (
        db.session.query(TicketType.name, func.count(Ticket.id), TicketType.valid_on, TicketType.sort_order)
        .join(OrderItem, OrderItem.ticket_type_id == TicketType.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Ticket, Ticket.order_item_id == OrderItem.id)
        .filter(Order.event_id == event_id, Order.payment_status == "paid")
        .group_by(TicketType.name, TicketType.valid_on, TicketType.sort_order)
        .all()
    )
    # By day first (undated types last), then the order the admin set on the ticket types.
    tickets_by_type_rows.sort(key=lambda r: (r[2] is None, r[2] or 0, r[3], r[0]))

    tickets_by_sale_mode_rows = (
        db.session.query(Payment.provider, func.count(Ticket.id))
        .select_from(Ticket)
        .join(OrderItem, Ticket.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Payment, Payment.order_id == Order.id)
        .filter(Order.event_id == event_id, Order.payment_status == "paid", Payment.status == "paid")
        .group_by(Payment.provider)
        .all()
    )

    # What each channel brought in: the amount charged on paid ticket payments (convenience fee included).
    channel_amounts = dict(
        db.session.query(Payment.provider, func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Payment.order_id == Order.id)
        .filter(
            Order.event_id == event_id,
            Order.payment_status == "paid",
            Payment.status == "paid",
            Payment.payment_type == "event_ticket",
        )
        .group_by(Payment.provider)
        .all()
    )

    top_expense_category_rows = (
        db.session.query(Expense.category, func.sum(Expense.amount))
        .filter(Expense.event_id == event_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .limit(3)
        .all()
    )

    # Per-coupon usage — orders_count/discount_total come from Order directly (one row per
    # order, however many items it has); tickets_by_type is a second, separate query (one row
    # per ticket) since a single order can mix several ticket types under the same coupon.
    # Both filter payment_status == "paid" to match every other stat on this endpoint.
    coupon_order_stats_rows = (
        db.session.query(
            Order.coupon_code,
            func.count(Order.id),
            func.coalesce(func.sum(Order.discount_amount), 0),
            func.coalesce(func.sum(Order.total_amount), 0),
        )
        .filter(
            Order.event_id == event_id,
            Order.payment_status == "paid",
            Order.coupon_code.isnot(None),
        )
        .group_by(Order.coupon_code)
        .all()
    )
    coupon_ticket_type_rows = (
        db.session.query(
            Order.coupon_code, TicketType.name, func.count(Ticket.id), TicketType.valid_on, TicketType.sort_order,
            TicketType.id, TicketType.coupon_eligible,
        )
        .select_from(Ticket)
        .join(OrderItem, Ticket.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(TicketType, OrderItem.ticket_type_id == TicketType.id)
        .filter(
            Order.event_id == event_id,
            Order.payment_status == "paid",
            Order.coupon_code.isnot(None),
        )
        .group_by(
            Order.coupon_code, TicketType.name, TicketType.valid_on, TicketType.sort_order,
            TicketType.id, TicketType.coupon_eligible,
        )
        .all()
    )
    coupons_by_code = {c.code: c for c in Coupon.query.filter_by(event_id=event_id).all()}
    # Only the tickets the coupon actually discounted: a ticket of another type in the same order was paid in
    # full (same rule as redemption_count_for_coupon). A coupon that has since been removed is judged by
    # coupon_eligible alone.
    coupon_ticket_type_rows = [
        r
        for r in coupon_ticket_type_rows
        if r[6] and (r[0] not in coupons_by_code or coupons_by_code[r[0]].applies_to_ticket_type(r[5]))
    ]
    coupon_ticket_type_rows.sort(key=lambda r: (r[3] is None, r[3] or 0, r[4], r[1]))
    coupon_ticket_types_by_code: dict[str, list[dict]] = {}
    for coupon_code, ticket_type_name, count, valid_on, _sort, _tt_id, _eligible in coupon_ticket_type_rows:
        coupon_ticket_types_by_code.setdefault(coupon_code, []).append(
            {"name": ticket_type_name, "count": count, "valid_on": valid_on.isoformat() if valid_on else None}
        )
    coupon_usage = sorted(
        (
            {
                "coupon_code": coupon_code,
                "orders_count": orders_count,
                "tickets_count": sum(
                    row["count"] for row in coupon_ticket_types_by_code.get(coupon_code, [])
                ),
                "discount_total": discount_total,
                # What the buyers paid after the discount, and what the same tickets cost before it.
                "paid_total": paid_total,
                "gross_total": paid_total + discount_total,
                "by_ticket_type": coupon_ticket_types_by_code.get(coupon_code, []),
                # The coupon's own setup (None when the coupon has since been removed).
                "discount_percent": coupons_by_code[coupon_code].discount_percent if coupon_code in coupons_by_code else None,
                "is_active": coupons_by_code[coupon_code].is_active if coupon_code in coupons_by_code else None,
                "max_redemptions": coupons_by_code[coupon_code].max_redemptions if coupon_code in coupons_by_code else None,
            }
            for coupon_code, orders_count, discount_total, paid_total in coupon_order_stats_rows
        ),
        key=lambda row: row["tickets_count"],
        reverse=True,
    )

    if not module_enabled("coupons"):
        coupon_usage = []  # a square without the Coupons module shows no coupon figures (W8-R21)

    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "slug": event.slug,
            "published": event.published,
            "start_datetime": event.start_datetime.isoformat(),
            "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
        },
        "collection_total": collection_total,
        "donations_total": donations_total,
        "pending_contributions": pending_contributions,
        "sponsorships_total": sponsorships_total,
        "expenses_total": expenses_total,
        "recorded_expenses_total": recorded_expenses_total,
        "processing_fees_total": processing_fees_total,
        "fees_by_provider": fees_by_provider,
        "net_total": collection_total - expenses_total,
        "tickets_sold": tickets_sold,
        "tickets_expected": tickets_expected,
        "tickets_checked_in": tickets_checked_in,
        "tickets_by_type": [
            {"name": name, "count": count, "valid_on": valid_on.isoformat() if valid_on else None}
            for name, count, valid_on, _sort in tickets_by_type_rows
        ],
        "tickets_by_sale_mode": [
            {"provider": provider, "count": count, "amount": int(channel_amounts.get(provider, 0))}
            for provider, count in tickets_by_sale_mode_rows
        ],
        "top_expense_categories": [
            {"category": category, "amount": amount} for category, amount in top_expense_category_rows
        ],
        "coupon_usage": coupon_usage,
    }


@admin_accounting_bp.get("/events/<int:event_id>/report")
def admin_accounting_event_report(event_id: int):
    """One-stop PDF of the whole accounting page for this event: the headline figures, the
    breakdown cards, coupon usage, every paid collection and every expense (never narrowed by the
    page's filters — a report should be complete), oldest first. Receipts are only marked Yes/No."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    now = datetime.now(timezone.utc)
    start = event.start_datetime if event.start_datetime.tzinfo else event.start_datetime.replace(tzinfo=timezone.utc)
    end = event.end_datetime
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    over = end if end is not None else start.replace(hour=23, minute=59, second=59)
    phase_label = "Draft" if not event.published else ("Expired" if over < now else "Live")

    orders = (
        Order.query.filter_by(event_id=event_id, payment_status="paid")
        .options(selectinload(Order.items).selectinload(OrderItem.ticket_type))
        .order_by(Order.created_at.asc(), Order.id.asc())
        .all()
    )
    payments = _latest_payment_by_order(orders)
    expenses = Expense.query.filter_by(event_id=event_id).order_by(Expense.date.asc(), Expense.id.asc()).all()
    contributions = (
        EventContribution.query.filter_by(event_id=event_id, status="paid")
        .order_by(EventContribution.date.asc(), EventContribution.id.asc())
        .all()
    )
    data = build_event_report_pdf(
        event=event,
        phase_label=phase_label,
        summary=_build_event_summary(event),
        collections=[_serialize_order_collection(o, payments.get(o.id)) for o in orders],
        expenses=[
            {
                "date": e.date.isoformat(),
                "description": e.description,
                "category": e.category,
                "amount": e.amount,
                "vendor": e.vendor,
                "notes": e.notes,
                "receipt_key": e.receipt_key,
            }
            for e in expenses
        ],
        contributions=[
            {"date": c.date.isoformat(), "kind": c.kind, "name": c.name, "method": c.payment_method, "amount": c.amount}
            for c in contributions
        ],
        provider_label=lambda value: label_for("payment_provider", value),
        category_label=lambda value: label_for("expense_category", value),
        generated_at=now,
        # "Show details" on the Collections table: a line under each order with what it bought.
        collection_details=request.args.get("details") in ("1", "true"),
    )
    return Response(
        data,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={event.slug}-accounting-report.pdf"},
    )


def _filtered_collection_orders(event_id: int, *, newest_first: bool) -> list[Order]:
    """The paid orders of an event that make up its Collections, narrowed by the current filters:
    `q` (order number, buyer name or email), `ticket_type_id` (orders containing any of those ticket types) and
    `payment_method` (the order's latest payment provider, or `coupon` for a free coupon order with no
    payment), `coupon_code` (orders that used any of those coupons); the last three take comma-separated lists. Shared by the page's list and the Excel export so the download matches what is shown."""
    stmt = select(Order).where(Order.event_id == event_id, Order.payment_status == "paid").options(
        selectinload(Order.items).selectinload(OrderItem.ticket_type)
    )
    stmt = stmt.order_by(*((Order.created_at.desc(),) if newest_first else (Order.created_at.asc(), Order.id.asc())))

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            db.or_(Order.order_number.ilike(like), Order.customer_name.ilike(like), Order.customer_email.ilike(like))
        )

    coupon_codes = [c.upper() for c in csv_arg("coupon_code")]
    if coupon_codes:
        stmt = stmt.where(Order.coupon_code.in_(coupon_codes))

    ticket_type_ids = csv_int_arg("ticket_type_id")
    if ticket_type_ids:
        stmt = stmt.where(
            select(OrderItem.id)
            .where(OrderItem.order_id == Order.id, OrderItem.ticket_type_id.in_(ticket_type_ids))
            .exists()
        )

    orders = list(db.session.scalars(stmt).all())

    methods = csv_arg("payment_method")
    if methods:
        payments = _latest_payment_by_order(orders)

        def method_of(order: Order) -> str | None:
            payment = payments.get(order.id)
            if payment:
                return payment.provider
            return "coupon" if order.coupon_code else None

        orders = [o for o in orders if method_of(o) in methods]
    return orders


@admin_accounting_bp.get("/events/<int:event_id>/collections")
def admin_accounting_event_collections(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    orders = _filtered_collection_orders(event_id, newest_first=True)
    payments = _latest_payment_by_order(orders)
    return jsonify({"items": [_serialize_order_collection(o, payments.get(o.id)) for o in orders]})


@admin_accounting_bp.get("/events/<int:event_id>/collections/export")
def admin_accounting_export_event_buyers(event_id: int):
    """Who bought tickets for this event — paid orders only. Sheet 1 "Buyers" has one row per
    order (contact details, what they bought, what they paid); sheet 2 "Tickets" has one row per
    individual ticket (its code and check-in state) — handy as a door list. Money is written as
    plain kroner, like every other export."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    orders = _filtered_collection_orders(event_id, newest_first=False)

    buyer_rows = []
    ticket_rows = []
    payments = _latest_payment_by_order(orders)
    for order in orders:
        payment = payments.get(order.id)
        paid_at = payment.paid_at if payment and payment.paid_at else order.created_at
        ticket_summary = ", ".join(
            _ticket_line(item) for item in sorted(order.items, key=lambda i: _ticket_type_day_key(i.ticket_type))
        )
        buyer_rows.append(
            [
                order.order_number,
                paid_at.strftime("%Y-%m-%d %H:%M"),
                order.customer_name,
                order.customer_email,
                order.customer_phone,
                ticket_summary,
                sum(item.quantity for item in order.items),
                order.coupon_code,
                order.discount_amount / 100 if order.discount_amount else None,
                order.total_amount / 100,
                payment.provider if payment else None,
            ]
        )
        for item in order.items:
            for ticket in item.tickets:
                checked_in_by = (
                    db.session.get(User, ticket.checked_in_by_user_id)
                    if ticket.checked_in_by_user_id
                    else None
                )
                ticket_rows.append(
                    [
                        ticket.ticket_code,
                        order.order_number,
                        order.customer_name,
                        order.customer_email,
                        order.customer_phone,
                        item.ticket_type.name if item.ticket_type else None,
                        ticket.status,
                        ticket.checked_in_at.strftime("%Y-%m-%d %H:%M") if ticket.checked_in_at else None,
                        (member_name_for_user(ticket.checked_in_by_user_id) or (checked_in_by.email if checked_in_by else None)),
                    ]
                )

    data = write_xlsx_sheets(
        [
            (
                "Buyers",
                [
                    "Order number", "Paid", "Name", "Email", "Phone", "Tickets", "Ticket count",
                    "Coupon", f"Discount ({site_currency()})", f"Amount paid ({site_currency()})", "Payment method",
                ],
                buyer_rows,
            ),
            (
                "Tickets",
                [
                    "Ticket code", "Order number", "Name", "Email", "Phone", "Ticket type",
                    "Status", "Checked in at", "Checked in by",
                ],
                ticket_rows,
            ),
            (
                "Donations & sponsors",
                ["Date", "Type", "From", "Email", "Method", f"Amount ({site_currency()})", "Notes"],
                [
                    [
                        c.date.isoformat(),
                        "Sponsorship" if c.kind == "sponsorship" else "Donation",
                        c.name,
                        c.email or "",
                        c.payment_method or "",
                        c.amount / 100,
                        c.notes or "",
                    ]
                    for c in EventContribution.query.filter_by(event_id=event_id, status="paid")
                    .order_by(EventContribution.date.asc(), EventContribution.id.asc())
                    .all()
                ],
            ),
        ]
    )
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={event.slug}-buyers.xlsx"},
    )


@admin_accounting_bp.get("/events/<int:event_id>/expenses/export")
def admin_accounting_export_event_expenses(event_id: int):
    """The expenses recorded for this event, oldest first, with a Total row at the bottom. With no
    filter it is every expense; it takes the same category / date_from / date_to / q filters as the
    list so the download can match what the page shows (the Total then covers only those rows). The
    receipt itself lives in the private bucket behind short-lived links, so the sheet only says
    whether one is attached. Money is plain kroner, like every other export."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    try:
        stmt = _filtered_expenses_stmt(event_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    expenses = db.session.scalars(stmt.order_by(Expense.date.asc(), Expense.id.asc())).all()
    rows = []
    for expense in expenses:
        creator = db.session.get(User, expense.created_by) if expense.created_by else None
        rows.append(
            [
                expense.date.isoformat(),
                expense.description,
                label_for("expense_category", expense.category),
                expense.vendor,
                expense.amount / 100,
                "Yes" if expense.receipt_key else "No",
                expense.notes,
                creator.email if creator else None,
            ]
        )
    if rows:
        rows.append(["Total", None, None, None, sum(e.amount for e in expenses) / 100, None, None, None])

    data = write_xlsx(
        ["Date", "Description", "Category", "Vendor", f"Amount ({site_currency()})", "Receipt attached", "Notes", "Added by"],
        rows,
    )
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={event.slug}-expenses.xlsx"},
    )


def _filtered_expenses_stmt(event_id: int | None):
    """An event's expenses narrowed by the current category / date range / search filters (unordered).
    Shared by the list and the Excel export so the download matches the page. Raises ValueError on a bad date."""
    stmt = select(Expense).where(Expense.event_id == event_id if event_id is not None else Expense.event_id.is_(None))

    categories = csv_arg("category")
    if categories:
        stmt = stmt.where(Expense.category.in_(categories))

    date_from = request.args.get("date_from")
    if date_from:
        try:
            stmt = stmt.where(Expense.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            raise ValueError("date_from must be YYYY-MM-DD") from None

    date_to = request.args.get("date_to")
    if date_to:
        try:
            stmt = stmt.where(Expense.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            raise ValueError("date_to must be YYYY-MM-DD") from None

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            db.or_(Expense.description.ilike(like), Expense.vendor.ilike(like))
        )
    return stmt


@admin_accounting_bp.get("/events/<int:event_id>/expenses")
def admin_accounting_list_expenses(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    try:
        stmt = _filtered_expenses_stmt(event_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    stmt = stmt.order_by(Expense.date.desc(), Expense.id.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_expense(e) for e in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
            # Read-only "<Provider> processing fees" lines the page shows above the recorded expenses.
            "processing_fee_lines": [
                {"provider": f["provider"], "amount": f["processing"]}
                for f in _fees_by_provider(event_id)
                if f["processing"]
            ],
        }
    )


@admin_accounting_bp.post("/events/<int:event_id>/expenses")
def admin_accounting_create_expense(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_expense_payload(data, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400

    expense = Expense(
        event_id=event_id,
        date=cleaned["date"],
        description=cleaned["description"],
        category=cleaned["category"],
        amount=cleaned["amount"],
        vendor=cleaned.get("vendor"),
        notes=cleaned.get("notes"),
        created_by=g.current_user.id,
    )
    db.session.add(expense)
    db.session.commit()

    return jsonify(_serialize_expense(expense)), 201


@admin_accounting_bp.patch("/expenses/<int:expense_id>")
def admin_accounting_update_expense(expense_id: int):
    expense = db.session.get(Expense, expense_id)
    if expense is None:
        return jsonify({"error": "Expense not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_expense_payload(data, is_create=False, current_category=expense.category)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(expense, field, value)

    db.session.commit()
    return jsonify(_serialize_expense(expense))


@admin_accounting_bp.delete("/expenses/<int:expense_id>")
def admin_accounting_delete_expense(expense_id: int):
    expense = db.session.get(Expense, expense_id)
    if expense is None:
        return jsonify({"error": "Expense not found"}), 404

    description = expense.description
    event_id = expense.event_id
    if expense.receipt_key:
        get_private_storage().delete(expense.receipt_key)
    db.session.delete(expense)
    db.session.commit()

    log_action(
        g.current_user,
        "expense_deleted",
        f'Deleted expense "{description}"',
        target_type="expense",
        target_id=expense_id,
    )

    return "", 204


@admin_accounting_bp.post("/expenses/<int:expense_id>/receipt")
def admin_accounting_upload_receipt(expense_id: int):
    expense = db.session.get(Expense, expense_id)
    if expense is None:
        return jsonify({"error": "Expense not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        data, content_type = validate_receipt(file)
    except ReceiptValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_private_storage()
    if expense.receipt_key:
        storage.delete(expense.receipt_key)

    safe_name = secure_filename(file.filename) or "receipt"
    storage_key = f"receipts/{expense.event_id}/{expense.id}-{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, data, content_type)

    expense.receipt_key = storage_key
    db.session.commit()

    return jsonify(_serialize_expense(expense))


@admin_accounting_bp.delete("/expenses/<int:expense_id>/receipt")
def admin_accounting_delete_receipt(expense_id: int):
    expense = db.session.get(Expense, expense_id)
    if expense is None:
        return jsonify({"error": "Expense not found"}), 404

    if expense.receipt_key:
        get_private_storage().delete(expense.receipt_key)
        expense.receipt_key = None
        db.session.commit()

    return jsonify(_serialize_expense(expense))


# The general book (W14-R15): expenses with no event, and income from the modules that take money without an event. Routes live in general.py.
from app.accounting import general  # noqa: E402,F401
from app.accounting import budget  # noqa: E402,F401  (W15-R18)
