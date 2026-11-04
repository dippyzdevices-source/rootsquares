from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_, select

from app.common.site import site_currency
from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.coupons.models import Coupon
from app.coupons.service import deactivate_coupon_if_limit_reached
from app.common.query_params import csv_arg, csv_int_arg
from app.extensions import db
from app.events.models import Event
from app.imports.excel import write_xlsx
from app.members.service import member_name_for_user
from app.orders.emails import (
    resend_tickets_confirmed_email,
    send_order_cancelled_email,
    send_order_rejected_email,
    send_tickets_confirmed_email,
)
from app.orders.models import Order
from app.orders.routes import _serialize_order
from app.orders.service import issue_tickets_for_order
from app.payments import vipps
from app.payments.fees import processing_fee_for
from app.payments import gateway
from app.payments.errors import GatewayError
from app.payments.methods import BANK, CASH, VIPPS_QR
from app.payments.models import Payment
from app.payments.service import get_payment_provider

admin_orders_bp = Blueprint("admin_orders", __name__, url_prefix="/api/admin/orders")
admin_orders_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50


def _customer_member_info(order: Order) -> dict:
    """Is the buyer a member? Matched by email, like everywhere else a roster entry is looked up.
    `member` = has an active membership, `former` = had one (expired/cancelled/suspended),
    `guest` = no membership (a roster entry without any, or nobody at all)."""
    from app.memberships.service import find_member_by_email

    member = find_member_by_email(order.customer_email or "")
    memberships = list(member.memberships) if member is not None else []  # newest first
    if not memberships:
        return {"status": "guest", "member_id": None, "membership_type": None, "photo_url": None}
    active = next((m for m in memberships if m.status == "active"), None)
    current = active or memberships[0]
    return {
        "status": "member" if active else "former",
        "member_id": member.id,
        "membership_type": current.membership_type,
        "photo_url": member.photo_url,
    }


def _serialize_order_admin(order: Order) -> dict:
    """Admin-only view of an order — adds who approved/rejected a payment-verification claim
    and why, plus who checked each ticket in and when, on top of the same fields the
    public/member serializer already returns. Never used by public/member routes, so this
    identity detail never leaks to non-admins (matching checked_in_by's existing admin-only
    treatment in app.checkin.admin_routes/app.tickets.admin_routes).
    """
    data = _serialize_order(order)
    approved_by = db.session.get(User, order.approved_by_user_id) if order.approved_by_user_id else None
    rejected_by = db.session.get(User, order.rejected_by_user_id) if order.rejected_by_user_id else None
    cancelled_by = db.session.get(User, order.cancelled_by_user_id) if order.cancelled_by_user_id else None
    data.update(
        {
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "customer_member": _customer_member_info(order),
            "approved_by_name": member_name_for_user(order.approved_by_user_id),
            "approved_by_email": approved_by.email if approved_by else None,
            "approved_at": order.approved_at.isoformat() if order.approved_at else None,
            "rejected_by_name": member_name_for_user(order.rejected_by_user_id),
            "rejected_by_email": rejected_by.email if rejected_by else None,
            "rejected_at": order.rejected_at.isoformat() if order.rejected_at else None,
            "rejection_reason": order.rejection_reason,
            "cancelled_by_name": member_name_for_user(order.cancelled_by_user_id),
            "cancelled_by_email": cancelled_by.email if cancelled_by else None,
            "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
            "cancellation_reason": order.cancellation_reason,
        }
    )

    # Every payment attempt for this order (newest first), so an admin can jump order -> payment.
    data["payments"] = [
        {
            "id": p.id,
            "payment_reference": p.payment_reference,
            "provider": p.provider,
            "amount": p.amount,
            "surcharge_amount": p.surcharge_amount or 0,
            # What the provider takes (an expense for the association, never charged to the customer);
            # payments from before fees were recorded are estimated with today's rates, as the accounting page does.
            "processing_fee_amount": p.processing_fee_amount
            if p.processing_fee_amount is not None
            else processing_fee_for(p.provider, p.amount),
            "status": p.status,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).all()
    ]

    tickets_by_id = {ticket.id: ticket for item in order.items for ticket in item.tickets}
    for item_data in data["items"]:
        for ticket_data in item_data["tickets"]:
            ticket = tickets_by_id[ticket_data["id"]]
            checked_in_by = (
                db.session.get(User, ticket.checked_in_by_user_id)
                if ticket.checked_in_by_user_id
                else None
            )
            ticket_data["issued_at"] = ticket.created_at.isoformat() if ticket.created_at else None
            ticket_data["checked_in_at"] = (
                ticket.checked_in_at.isoformat() if ticket.checked_in_at else None
            )
            ticket_data["checked_in_by_email"] = checked_in_by.email if checked_in_by else None
            ticket_data["checked_in_by_name"] = member_name_for_user(ticket.checked_in_by_user_id)

    return data


def _filtered_orders_stmt():
    """The orders query for the current event / payment status / search filters. Shared by the list and
    the Excel export so the download always matches what the page shows. Raises ValueError on a bad event_id."""
    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    event_ids = csv_int_arg("event_id")
    if event_ids:
        stmt = stmt.where(Order.event_id.in_(event_ids))
    # Comma-separated so a caller can ask for several at once, e.g. the dashboard's
    # "needs action" banner (pending,pending_verification).
    payment_statuses = csv_arg("payment_status")
    if payment_statuses:
        stmt = stmt.where(Order.payment_status.in_(payment_statuses))
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Order.order_number.ilike(like),
                Order.customer_name.ilike(like),
                Order.customer_email.ilike(like),
                Order.customer_phone.ilike(like),
            )
        )
    return stmt


@admin_orders_bp.get("")
def admin_list_orders():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    try:
        stmt = _filtered_orders_stmt()
    except ValueError:
        return jsonify({"error": "event_id must be an integer"}), 400

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_order_admin(o) for o in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_orders_bp.get("/export")
def admin_export_orders():
    try:
        orders = db.session.scalars(_filtered_orders_stmt()).all()
    except ValueError:
        return jsonify({"error": "event_id must be an integer"}), 400
    event_titles = {e.id: e.title for e in Event.query.all()}

    headers = [
        "Order number", "Customer name", "Customer email", "Event", "Ticket type",
        "Quantity", f"Unit price ({site_currency()})", f"Subtotal ({site_currency()})", "Payment status", "Order status",
        "Created at",
    ]
    rows = []
    for order in orders:
        for item in order.items:
            rows.append(
                [
                    order.order_number,
                    order.customer_name,
                    order.customer_email,
                    event_titles.get(order.event_id),
                    item.ticket_type.name if item.ticket_type else None,
                    item.quantity,
                    item.unit_price / 100,
                    item.subtotal / 100,
                    order.payment_status,
                    order.order_status,
                    order.created_at.isoformat(),
                ]
            )

    data = write_xlsx(headers, rows)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=orders.xlsx"},
    )


@admin_orders_bp.get("/<int:order_id>")
def admin_get_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(_serialize_order_admin(order))


def _cancel_vipps_attempt(payment: Payment) -> None:
    """Best effort: an open online attempt (Vipps app or Stripe card) has charged nothing yet, so cancelling is always safe."""
    if payment.status == "initiated":
        payment.status = "cancelled"
        if payment.provider_transaction_id:
            try:
                gateway.client_for(payment.provider).cancel(payment.provider_transaction_id)
            except (GatewayError, KeyError):
                pass


@admin_orders_bp.post("/<int:order_id>/mark-paid")
def admin_mark_paid(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found"}), 404

    if order.payment_status == "paid":
        return jsonify(_serialize_order_admin(order))  # idempotent no-op — see Global Constraints

    # "pending" is allowed too: buyers (often committee members) frequently pay without ever
    # clicking "I've paid", and admins must still be able to confirm those.
    if order.payment_status not in ("pending", "pending_verification"):
        return jsonify({"error": "Only unpaid orders can be marked as paid."}), 409

    data = request.get_json(silent=True) or {}
    paid_with = data.get("payment_method")
    if paid_with not in (None, CASH, VIPPS_QR, BANK):
        return jsonify({"errors": {"payment_method": "Must be cash, vipps_qr or bank_transfer."}}), 400
    payment = (
        Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).first()
    )
    if payment is not None and payment.provider in gateway.ONLINE_PROVIDERS:
        # The customer started an online (Vipps app or card) payment but this order is being settled another way
        # (e.g. cash/QR). Release the Vipps attempt so it can never also charge them.
        _cancel_vipps_attempt(payment)
        payment = None
    if payment is not None:
        if paid_with:
            payment.provider = paid_with  # the admin states how it was actually paid
        get_payment_provider().confirm_payment(payment)

    order.payment_status = "paid"
    order.order_status = "confirmed"
    order.approved_by_user_id = g.current_user.id
    order.approved_at = datetime.now(timezone.utc)

    issue_tickets_for_order(order)

    db.session.commit()

    log_action(
        g.current_user,
        "order_marked_paid",
        f"Marked order {order.order_number} as paid" + (f" ({paid_with})" if paid_with else ""),
        target_type="order",
        target_id=order.id,
    )

    if order.coupon_id:
        coupon = db.session.get(Coupon, order.coupon_id)
        if coupon is not None:
            deactivate_coupon_if_limit_reached(coupon)

    send_tickets_confirmed_email(order)

    return jsonify(_serialize_order_admin(order))


@admin_orders_bp.post("/<int:order_id>/resend-confirmation")
def admin_resend_confirmation(order_id: int):
    """Send the tickets-confirmed email (with the QR codes) to the buyer again. Only for a paid order —
    that is the only state with tickets to send. Answers 502 when the mail service refuses, so the admin
    knows it did not go out."""
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found"}), 404
    if order.payment_status != "paid":
        return jsonify({"error": "Only a paid order has tickets to send."}), 409
    if not resend_tickets_confirmed_email(order):
        return jsonify({"error": "The email could not be sent. Please try again shortly."}), 502
    return jsonify({"sent_to": order.customer_email})


@admin_orders_bp.post("/<int:order_id>/reject")
def admin_reject_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found"}), 404

    if order.payment_status == "rejected":
        return jsonify(_serialize_order_admin(order))  # idempotent no-op, same as mark-paid

    # "pending" is allowed too, mirroring mark-paid's own precedent just above — an admin must
    # be able to reject an order that was never even claimed as paid (e.g. a stale/abandoned
    # cash order), not only one a buyer explicitly flagged via "I've paid".
    if order.payment_status not in ("pending", "pending_verification"):
        return jsonify({"error": "Only unpaid orders can be rejected."}), 409

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"errors": {"reason": "This field is required."}}), 400

    open_vipps = Payment.query.filter(
        Payment.order_id == order.id, Payment.provider.in_(gateway.ONLINE_PROVIDERS), Payment.status == "initiated"
    ).all()
    for attempt in open_vipps:
        _cancel_vipps_attempt(attempt)

    order.payment_status = "rejected"
    order.order_status = "cancelled"
    order.rejected_by_user_id = g.current_user.id
    order.rejected_at = datetime.now(timezone.utc)
    order.rejection_reason = reason
    db.session.commit()

    log_action(
        g.current_user,
        "order_rejected",
        f"Rejected order {order.order_number}: {reason}",
        target_type="order",
        target_id=order.id,
    )

    send_order_rejected_email(order, reason)

    return jsonify(_serialize_order_admin(order))


@admin_orders_bp.post("/<int:order_id>/cancel")
def admin_cancel_order(order_id: int):
    """Cancel an already-paid, tickets-issued order — distinct from reject (admin_reject_order
    above), which only ever applies pre-payment. Confirmed with the user before building this:
    an order with any "used" (checked-in) ticket can no longer be cancelled (409) — its holder
    already physically entered and that can't be undone.

    Moving payment_status off "paid" is also what frees up any coupon capacity this order
    consumed: coupons.models.redemption_count_for_coupon() only ever counts tickets on
    payment_status == "paid" orders, so a cancelled order's tickets stop counting the moment
    this commits — no coupon-specific code needed here. A coupon already auto-deactivated
    (Coupon.is_active) by hitting its max_redemptions is NOT automatically reactivated by this —
    an admin can flip it back on from the coupon editor if the freed-up capacity should be used.
    """
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found"}), 404

    if order.payment_status == "cancelled":
        return jsonify(_serialize_order_admin(order))  # idempotent no-op, same as mark-paid/reject

    if order.payment_status != "paid":
        return (
            jsonify({"error": "Only a paid order with issued tickets can be cancelled."}),
            409,
        )

    if any(t.status == "used" for item in order.items for t in item.tickets):
        return (
            jsonify({"error": "This order cannot be cancelled: a ticket has already been checked in."}),
            409,
        )

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"errors": {"reason": "This field is required."}}), 400

    for item in order.items:
        for ticket in item.tickets:
            if ticket.status == "valid":
                ticket.status = "void"

    order.payment_status = "cancelled"
    order.order_status = "cancelled"
    order.cancelled_by_user_id = g.current_user.id
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancellation_reason = reason
    db.session.commit()

    log_action(
        g.current_user,
        "order_cancelled",
        f"Cancelled order {order.order_number}: {reason}",
        target_type="order",
        target_id=order.id,
    )

    send_order_cancelled_email(order, reason)

    return jsonify(_serialize_order_admin(order))
