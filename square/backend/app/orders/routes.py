import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from app.common.phone import is_valid_phone
from app.common.site import site_currency, site_phone_rule
from app.common.site import order_prefix, site_name
from app.auth.decorators import require_auth
from app.auth.models import User
from app.auth.service import resolve_user_from_token
from app.coupons.models import Coupon, redemption_count_for_coupon
from app.modules import module_enabled
from app.coupons.service import deactivate_coupon_if_limit_reached
from app.events.models import Event
from app.extensions import db
from app.orders.emails import (
    send_bank_order_received_email,
    send_cash_order_received_email,
    send_order_awaiting_verification_email,
    send_order_received_email,
    send_payment_notification_received_email,
    send_tickets_confirmed_email,
)
from app.orders.models import Order, OrderItem
from app.orders.service import allowed_payment_methods, cash_note_for_event, issue_tickets_for_order
from app.common.urls import frontend_base_url
from app.payments import vipps
from app.payments.bank import bank_details
from app.payments.fees import convenience_fee_for
from app.payments import gateway
from app.payments.errors import GatewayError
from app.payments.methods import BANK, CASH, STRIPE, VIPPS_QR
from app.payments.models import Payment
from app.payments.service import get_payment_provider
from app.settings.models import get_site_settings
from app.tickets.models import TicketType
from app.tickets.qr import generate_qr_data_url
from app.tickets.routes import _sold_count, _ticket_type_status

# Ticket-count limits are per event (Event.max_tickets_per_email / coupon_max_adult /
# coupon_max_child, all optional — null = no limit), set in the admin event form:
#  - max_tickets_per_email: one email can reserve at most this many tickets of a given ticket
#    type across every order it's placed (a general anti-abuse cap, independent of coupons;
#    per ticket type so a family can buy e.g. 4 Adult and 4 Child for the same event).
#  - coupon_max_adult / coupon_max_child: an order using a coupon can include at most this many
#    coupon-eligible adult, and separately child, tickets.
# Statuses that don't represent a live claim on tickets, so they're excluded from the count
# above — an order that ends up here frees the email to be used again for this ticket type.
# "failed"/"refunded" are included on the same reasoning even though nothing in this codebase
# currently sets them on a ticket order (see the Payments section of CLAUDE.md) — they mean
# "this didn't happen" just as much as cancelled/rejected do.
NON_RESERVING_PAYMENT_STATUSES = ("cancelled", "rejected", "failed", "refunded")

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _tickets_reserved_for_email(ticket_type_id: int, email: str) -> int:
    """Total ticket quantity this email has already reserved for this ticket type, across every
    order that isn't cancelled/rejected/failed/refunded (see NON_RESERVING_PAYMENT_STATUSES)
    — compared case-insensitively, matching lookup_order/confirm_payment's own email
    comparison convention."""
    total = (
        db.session.query(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            OrderItem.ticket_type_id == ticket_type_id,
            func.lower(Order.customer_email) == email.strip().lower(),
            Order.payment_status.notin_(NON_RESERVING_PAYMENT_STATUSES),
        )
        .scalar()
    )
    return total or 0


def _optional_user() -> User | None:
    """Like auth.decorators._authenticate, but never rejects — checkout always allows a
    guest. Still JIT-provisions a local User the same way any other authenticated request
    does, so a logged-in buyer's order links to their account.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    return resolve_user_from_token(token)



def _unavailable_message(provider) -> str:
    return "Card payment is not available right now." if provider == STRIPE else "Vipps app payment is not available right now."


def _start_failed_message(provider) -> str:
    return "Could not start the card payment. Please try again." if provider == STRIPE else "Could not start the Vipps payment. Please try again."


def _serialize_order_item(item: OrderItem) -> dict:
    return {
        "id": item.id,
        "ticket_type_id": item.ticket_type_id,
        "ticket_type_name": item.ticket_type.name if item.ticket_type else None,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "subtotal": item.subtotal,
        "tickets": [
            {
                "id": t.id,
                "ticket_code": t.ticket_code,
                "status": t.status,
                "qr_code_data_url": generate_qr_data_url(t.ticket_code),
            }
            for t in item.tickets
        ],
    }


def _serialize_order(order: Order) -> dict:
    event = db.session.get(Event, order.event_id)
    latest_payment = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    coupon = db.session.get(Coupon, order.coupon_id) if order.coupon_id else None
    return {
        "id": order.id,
        "order_number": order.order_number,
        "event_id": order.event_id,
        "event_title": event.title if event else None,
        "event_start_datetime": event.start_datetime.isoformat() if event else None,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "customer_phone": order.customer_phone,
        "total_amount": order.total_amount,
        "coupon_code": order.coupon_code,
        # The coupon's percentage (read from the coupon itself; null if it no longer exists).
        "coupon_percent": coupon.discount_percent if coupon else None,
        "discount_amount": order.discount_amount,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "payment_method": latest_payment.provider if latest_payment else None,
        "cash_note": cash_note_for_event(event) if latest_payment and latest_payment.provider == CASH else "",
        "bank": bank_details(get_site_settings()) if latest_payment and latest_payment.provider == BANK else None,
        "items": [_serialize_order_item(i) for i in order.items],
        "created_at": order.created_at.isoformat(),
    }


@orders_bp.post("")
def checkout():
    data = request.get_json(silent=True) or {}

    errors: dict[str, str] = {}
    if not data.get("customer_name") or not isinstance(data["customer_name"], str):
        errors["customer_name"] = "This field is required."
    if not data.get("customer_email") or not isinstance(data["customer_email"], str):
        errors["customer_email"] = "This field is required."
    elif not EMAIL_RE.match(data["customer_email"].strip()):
        errors["customer_email"] = "Enter a valid email address."
    customer_phone = data.get("customer_phone")
    if not customer_phone or not isinstance(customer_phone, str) or not customer_phone.strip():
        errors["customer_phone"] = "This field is required."
    elif not is_valid_phone(customer_phone, site_phone_rule()):
        errors["customer_phone"] = site_phone_rule().message()
    items_payload = data.get("items")
    if not items_payload or not isinstance(items_payload, list):
        errors["items"] = "At least one ticket item is required."
    if errors:
        return jsonify({"errors": errors}), 400

    event_id = data.get("event_id")
    event = db.session.get(Event, event_id) if event_id else None
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    # Resolved here (rather than down near Order creation, where this used to happen) so it can
    # also decide the published-gate below — an admin's own authenticated checkout can buy a
    # test ticket for a draft event, so they can exercise the real purchase flow before the
    # event goes live (see the matching note on app.events.routes.get_event). Still reused
    # further down for the order's own user_id attribution, unchanged.
    user = _optional_user()
    is_admin = user is not None and user.role == "admin"
    if not event.published and not is_admin:
        return jsonify({"error": "Event not found"}), 404

    now = datetime.now(timezone.utc)
    cleaned_items: list[dict] = []
    for raw_item in items_payload:
        ticket_type_id = raw_item.get("ticket_type_id")
        quantity = raw_item.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return jsonify({"errors": {"items": "Each item needs a positive quantity."}}), 400

        ticket_type = db.session.get(TicketType, ticket_type_id)
        if ticket_type is None or ticket_type.event_id != event.id:
            return jsonify({"errors": {"items": "One or more ticket types are invalid for this event."}}), 400

        status = _ticket_type_status(
            ticket_type,
            None if ticket_type.capacity is None else max(ticket_type.capacity - _sold_count(ticket_type.id), 0),
        )
        if status == "upcoming" and event.sales_not_open:
            return jsonify({"errors": {"items": "Ticket sales for this event have not opened yet."}}), 400
        if status == "ended" and event.sales_closed:
            return jsonify({"errors": {"items": "Ticket sales for this event have closed."}}), 400
        if status in ("upcoming", "ended"):
            return jsonify({"errors": {"items": "One or more ticket types are not currently on sale."}}), 400

        if ticket_type.capacity is not None:
            remaining = ticket_type.capacity - _sold_count(ticket_type.id)
            if quantity > remaining:
                return jsonify({"errors": {"items": "Not enough tickets remaining for one or more ticket types."}}), 400

        cleaned_items.append({"ticket_type": ticket_type, "quantity": quantity})

    # A "child" ticket is never sold on its own — every order with one must include at least
    # one "adult" ticket too (an "other"-category item present doesn't satisfy this).
    has_child = any(item["ticket_type"].age_category == "child" for item in cleaned_items)
    has_adult = any(item["ticket_type"].age_category == "adult" for item in cleaned_items)
    if has_child and not has_adult:
        return (
            jsonify(
                {"errors": {"items": "An order with a child ticket must also include an adult ticket."}}
            ),
            400,
        )

    # Per-ticket-type, per-email cap — independent of coupons, checked against every prior
    # order this email placed for each requested ticket type that hasn't been
    # cancelled/rejected/failed/refunded. Grouped by ticket_type_id first in case the same type
    # appears in more than one line item.
    requested_by_type: dict[int, int] = {}
    for item in cleaned_items:
        tt_id = item["ticket_type"].id
        requested_by_type[tt_id] = requested_by_type.get(tt_id, 0) + item["quantity"]

    email_cap = event.max_tickets_per_email
    for tt_id, requested_qty in requested_by_type.items():
        if email_cap is None:
            break
        already_reserved = _tickets_reserved_for_email(tt_id, data["customer_email"])
        if already_reserved + requested_qty > email_cap:
            remaining = max(email_cap - already_reserved, 0)
            ticket_type_name = next(
                item["ticket_type"].name for item in cleaned_items if item["ticket_type"].id == tt_id
            )
            return (
                jsonify(
                    {
                        "errors": {
                            "customer_email": (
                                f"This email address can reserve at most "
                                f"{email_cap} \"{ticket_type_name}\" "
                                f"tickets — {remaining} remaining, but this order requests "
                                f"{requested_qty}."
                            )
                        }
                    }
                ),
                400,
            )

    subtotal_amount = sum(item["ticket_type"].price * item["quantity"] for item in cleaned_items)

    coupon = None
    discount_amount = 0
    coupon_code_raw = data.get("coupon_code")
    if coupon_code_raw and not module_enabled("coupons"):
        # A square without the Coupons module takes no coupon, even one that is still stored (W8-R21)
        return jsonify({"errors": {"coupon_code": "Invalid or inactive coupon code."}}), 400
    if coupon_code_raw:
        if not isinstance(coupon_code_raw, str) or not coupon_code_raw.strip():
            return jsonify({"errors": {"coupon_code": "Enter a valid coupon code."}}), 400

        coupon = Coupon.query.filter_by(
            event_id=event.id, code=coupon_code_raw.strip().upper(), is_active=True
        ).first()
        if coupon is None:
            return jsonify({"errors": {"coupon_code": "Invalid or inactive coupon code."}}), 400

        # Hard cap on total tickets ever issued under this coupon (see Coupon.max_redemptions'
        # own docstring) — checked BEFORE the order is created, against this order's own
        # requested quantity, so a single large order can never push the running total past the
        # limit. deactivate_coupon_if_limit_reached() (called after payment, below) only flips
        # is_active for admin/public display once the cap is reached — this is the real gate.
        if coupon.max_redemptions is not None:
            # Only the tickets the coupon will actually discount count as uses.
            requested_qty = sum(
                item["quantity"]
                for item in cleaned_items
                if item["ticket_type"].coupon_eligible and coupon.applies_to_ticket_type(item["ticket_type"].id)
            )
            already_used = redemption_count_for_coupon(coupon.id)
            remaining = coupon.max_redemptions - already_used
            if requested_qty > remaining:
                return (
                    jsonify(
                        {
                            "errors": {
                                "coupon_code": (
                                    f"This coupon only has {max(remaining, 0)} use(s) left."
                                )
                            }
                        }
                    ),
                    400,
                )

        # A coupon never discounts an ineligible ticket type (TicketType.coupon_eligible), nor
        # one outside its own allow-list if it has one (Coupon.applies_to_ticket_type — e.g.
        # "member" allowed on Adult while "sanatan" isn't, even though both are coupon_eligible
        # types) — those items are still charged in full, alongside a discount on the eligible
        # ones.
        eligible_items = [
            item
            for item in cleaned_items
            if item["ticket_type"].coupon_eligible and coupon.applies_to_ticket_type(item["ticket_type"].id)
        ]
        if not eligible_items:
            return (
                jsonify(
                    {"errors": {"coupon_code": "None of the selected ticket types are eligible for this coupon."}}
                ),
                400,
            )

        adult_qty = sum(
            item["quantity"] for item in eligible_items if item["ticket_type"].age_category == "adult"
        )
        child_qty = sum(
            item["quantity"] for item in eligible_items if item["ticket_type"].age_category == "child"
        )
        too_many_adult = event.coupon_max_adult is not None and adult_qty > event.coupon_max_adult
        too_many_child = event.coupon_max_child is not None and child_qty > event.coupon_max_child
        if too_many_adult or too_many_child:
            limits = []
            if event.coupon_max_adult is not None:
                limits.append(f"{event.coupon_max_adult} adult")
            if event.coupon_max_child is not None:
                limits.append(f"{event.coupon_max_child} child")
            return (
                jsonify(
                    {
                        "errors": {
                            "coupon_code": (
                                f"An order using a coupon can include at most "
                                f"{' and '.join(limits)} coupon-eligible tickets."
                            )
                        }
                    }
                ),
                400,
            )

        eligible_subtotal = sum(item["ticket_type"].price * item["quantity"] for item in eligible_items)
        # Round-half-up in whole øre — a 100% coupon always resolves the eligible portion to
        # exactly 0, never a stray fraction. Ineligible items are never part of this sum, so
        # they're always charged in full regardless of the coupon's percentage.
        discount_amount = (eligible_subtotal * coupon.discount_percent + 50) // 100

    total_amount = subtotal_amount - discount_amount

    if total_amount > 0:
        requested_method = {vipps.PROVIDER: "app", CASH: "cash", BANK: "bank", STRIPE: "card"}.get(data.get("payment_method"), "qr")
        if requested_method in ("app", "card") and not gateway.is_public(data.get("payment_method")):
            return jsonify({"error": _unavailable_message(data.get("payment_method"))}), 503
        allowed = allowed_payment_methods(event)
        if requested_method not in allowed:
            names = {"qr": "Vipps-QR", "app": "Vipps-App", "bank": "Bank transfer", "cash": "Cash", "card": "Card"}
            accepted = " or ".join(names[m] for m in ("qr", "app", "bank", "cash", "card") if m in allowed)
            return (
                jsonify({"errors": {"payment_method": f"This event only accepts payment with {accepted}."}}),
                400,
            )

    order = Order(
        order_number="PENDING",  # replaced below once flush() gives us a real id
        event_id=event.id,
        user_id=user.id if user else None,
        customer_name=data["customer_name"].strip(),
        customer_email=data["customer_email"].strip(),
        customer_phone=data.get("customer_phone") or None,
        total_amount=total_amount,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        discount_amount=discount_amount,
    )
    db.session.add(order)
    db.session.flush()
    order.order_number = f"{order_prefix()}-{order.created_at.year}-{order.id:06d}"

    for item in cleaned_items:
        subtotal = item["ticket_type"].price * item["quantity"]
        db.session.add(
            OrderItem(
                order_id=order.id,
                ticket_type_id=item["ticket_type"].id,
                quantity=item["quantity"],
                unit_price=item["ticket_type"].price,
                subtotal=subtotal,
            )
        )
    db.session.flush()

    if total_amount == 0:
        # No payment to collect (a 100% coupon, or a naturally free ticket type) — issue
        # tickets immediately rather than showing a Vipps panel for nothing to pay.
        order.payment_status = "paid"
        order.order_status = "confirmed"
        issue_tickets_for_order(order)
        db.session.commit()
        if coupon is not None:
            deactivate_coupon_if_limit_reached(coupon)
        send_tickets_confirmed_email(order)
    elif data.get("payment_method") in gateway.ONLINE_PROVIDERS:
        # Pay online (Vipps app or Stripe card): charged total = order total + the convenience fee, confirmed by the provider
        # itself (webhook / return-page check, see app.payments.vipps.sync_vipps_payment). No "pay via Vipps QR" email: the
        # confirmation email goes out once it is actually paid.
        provider = data["payment_method"]
        if not gateway.is_public(provider):
            db.session.rollback()
            return jsonify({"error": _unavailable_message(provider)}), 503
        surcharge = convenience_fee_for(provider, total_amount)
        payment = Payment(
            payment_type="event_ticket", order_id=order.id, provider=provider,
            amount=total_amount + surcharge, surcharge_amount=surcharge or None,
            currency=site_currency(), status="initiated",
        )
        db.session.add(payment)
        db.session.flush()
        payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
        try:
            redirect_url = gateway.start_payment(
                payment, f"{frontend_base_url()}/orders/vipps-return?ref={{ref}}", f"{site_name()} tickets {order.order_number}"
            )
        except GatewayError:
            db.session.rollback()  # no order is left behind if the provider refuses
            return jsonify({"error": _start_failed_message(provider)}), 502
        db.session.commit()
        body = _serialize_order(order)
        body["redirect_url"] = redirect_url
        body["surcharge_amount"] = payment.surcharge_amount or 0
        return jsonify(body), 201
    elif data.get("payment_method") == BANK:
        # Bank transfer: the buyer gets the square's account details and the order number as the reference; an admin confirms when the money arrived.
        get_payment_provider().create_payment(order, method=BANK)
        db.session.commit()
        send_bank_order_received_email(order)
    elif data.get("payment_method") == CASH:
        # Cash: no QR and no "I have paid" step — the order stays pending until an admin confirms
        # the money was received (mark-paid), and only then do the tickets exist.
        get_payment_provider().create_payment(order, method=CASH)
        db.session.commit()
        send_cash_order_received_email(order)
    else:
        get_payment_provider().create_payment(order, method=VIPPS_QR)
        db.session.commit()
        send_order_received_email(order)

    return jsonify(_serialize_order(order)), 201


@orders_bp.get("/lookup")
def lookup_order():
    order_number = request.args.get("order_number", "")
    email = request.args.get("email", "")
    order = Order.query.filter_by(order_number=order_number).first()
    if order is None or order.customer_email.lower() != email.strip().lower():
        return jsonify({"error": "Order not found"}), 404
    return jsonify(_serialize_order(order))


@orders_bp.post("/<order_number>/confirm-payment")
def confirm_payment(order_number: str):
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    order = Order.query.filter_by(order_number=order_number).first()
    if order is None or order.customer_email.lower() != email.strip().lower():
        return jsonify({"error": "Order not found"}), 404

    if order.payment_status != "pending":
        return jsonify({"error": "This order is not awaiting a payment report."}), 409
    latest = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    if latest is not None and latest.provider == CASH:
        return jsonify({"error": "This is a cash order — an admin confirms it once you have paid."}), 409

    order.payment_status = "pending_verification"
    db.session.commit()

    send_payment_notification_received_email(order)
    send_order_awaiting_verification_email(order)

    return jsonify(_serialize_order(order))


@orders_bp.get("/me")
@require_auth
def my_orders():
    from flask import g

    return jsonify({"items": [_serialize_order(o) for o in orders_for_user(g.current_user)]})


def orders_for_user(user):
    # Guest orders (user_id NULL) placed with this account's email before it registered also belong to it.
    match = Order.user_id == user.id
    if user.email:
        match = or_(match, func.lower(Order.customer_email) == user.email.strip().lower())
    return Order.query.filter(match).order_by(Order.created_at.desc()).all()
