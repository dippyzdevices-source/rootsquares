"""Admin payment reconciliation, export, and refund. Covers both payment_type values — the
Payment table is shared between ticket and membership money, so this is the one place an admin
answers "what happened to this payment," "which months did it settle," and "which payments
belong to this member," regardless of which kind of payment it is.
"""

from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_, select

from app.common.site import site_currency, site_timezone
from app.common.site import site_name
from app.audit.service import log_action
from app.common.urls import frontend_base_url
from app.auth.decorators import require_role
from app.common.query_params import csv_arg
from app.extensions import db
from app.imports.excel import write_xlsx
from app.events.models import Event
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod
from app.memberships.service import activate_pending_memberships_after_payment
from app.orders.emails import send_order_refunded_email
from app.orders.models import Order
from app.payments import gateway, stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.fees import convenience_fee_for, snapshot_processing_fee
from app.payments.models import Payment, PaymentAllocation

admin_payments_bp = Blueprint("admin_payments", __name__, url_prefix="/api/admin/payments")
admin_payments_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
VALID_PAYMENT_TYPES = {"event_ticket", "membership", "donation", "event_donation", "vipps_test"}


def _member_for_membership_payment(payment: Payment) -> Member | None:
    if payment.payment_type != "membership":
        return None
    allocation = PaymentAllocation.query.filter_by(payment_id=payment.id).first()
    if allocation is None:
        return None
    period = db.session.get(MembershipPeriod, allocation.membership_period_id)
    membership = db.session.get(Membership, period.membership_id) if period else None
    return db.session.get(Member, membership.member_id) if membership else None


def _payer_info_for_payment(payment: Payment) -> tuple[str | None, str | None]:
    """Who paid, as (name, email) — a Member for a membership payment, or the guest/customer
    details recorded on the Order for a ticket payment. The two payment types don't share an
    identity model (a ticket buyer need not be a Member at all), so this is the one place that
    resolves either into a single display identity for the shared admin reconciliation list.
    """
    if payment.payment_type == "membership":
        allocation = PaymentAllocation.query.filter_by(payment_id=payment.id).first()
        if allocation is None:
            return None, None
        period = db.session.get(MembershipPeriod, allocation.membership_period_id)
        membership = db.session.get(Membership, period.membership_id)
        member = db.session.get(Member, membership.member_id)
        return (member.name, member.email) if member else (None, None)

    if payment.payment_type == "event_donation":
        from app.accounting.models import EventContribution

        donation = EventContribution.query.filter_by(payment_id=payment.id).first()
        return (donation.name, donation.email) if donation else (None, None)

    if payment.payment_type == "vipps_test":
        # The admin 1 kr test payment has no order or member to name — label it instead of "—".
        return "Vipps test payment (admin)", None

    if payment.payment_type == "donation":
        from app.donations.models import Donation

        donation = db.session.get(Donation, payment.donation_id) if payment.donation_id else None
        return (donation.donor_name, donation.donor_email) if donation else (None, None)

    if payment.order_id is None:
        return None, None
    order = db.session.get(Order, payment.order_id)
    return (order.customer_name, order.customer_email) if order else (None, None)


def _refund_block_reason(payment: Payment) -> str | None:
    """Why a (ticket) payment may not be refunded, or None. Membership payments have no event
    and no entry, so they are never blocked here."""
    if payment.payment_type != "event_ticket" or payment.order_id is None:
        return None
    order = db.session.get(Order, payment.order_id)
    if order is None:
        return None
    event = db.session.get(Event, order.event_id)
    if event is not None:
        end = event.end_datetime or event.start_datetime
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        zone = site_timezone()  # the square's own time zone, not Oslo (rootsquares W6-R54)
        if datetime.now(zone).date() > end.astimezone(zone).date():
            return "Refunds are not allowed after the event day."
    if any(t.status == "used" for item in order.items for t in item.tickets):
        return "A ticket on this order has already been used for entry, so it can't be refunded."
    return None


def _serialize_payment_admin(payment: Payment) -> dict:
    allocations = []
    if payment.payment_type == "membership":
        rows = (
            PaymentAllocation.query.filter_by(payment_id=payment.id)
            .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
            .add_columns(MembershipPeriod.label)
            .all()
        )
        allocations = [{"amount": a.amount, "label": label} for a, label in rows]

    payer_name, payer_email = _payer_info_for_payment(payment)
    order = db.session.get(Order, payment.order_id) if payment.order_id else None
    member = _member_for_membership_payment(payment)
    return {
        "id": payment.id,
        "member_id": member.id if member else None,
        "order_number": order.order_number if order else None,
        "payment_reference": payment.payment_reference,
        "payment_type": payment.payment_type,
        "payer_name": payer_name,
        "payer_email": payer_email,
        "order_id": payment.order_id,
        "provider": payment.provider,
        "amount": payment.amount,
        "surcharge_amount": payment.surcharge_amount or 0,
        # "vipps": we send the money back through Vipps ourselves; "manual" (cash, Vipps QR): the association must
        # return the money by hand BEFORE marking the payment refunded.
        "refund_mode": "vipps" if payment.provider == vipps.PROVIDER else "stripe" if payment.provider == stripe_gateway.PROVIDER else "manual",
        "refund_blocked_reason": _refund_block_reason(payment) if payment.status == "paid" else None,
        "currency": payment.currency,
        "status": payment.status,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "created_at": payment.created_at.isoformat(),
        # Last time the payment row changed (status flips such as paid/refunded/rejected).
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
        "allocations": allocations,
    }


def _filtered_payments_stmt():
    """The payments query for the current type / status / provider / search filters. Shared by the list and
    the Excel export so the download always matches what the page shows. Raises ValueError on a bad payment_type."""
    stmt = select(Payment).order_by(Payment.created_at.desc())

    # payment_type / status / provider each take several comma-separated values (OR within a filter).
    payment_types = csv_arg("payment_type")
    if payment_types:
        if any(t not in VALID_PAYMENT_TYPES for t in payment_types):
            raise ValueError(f"payment_type must be one of {sorted(VALID_PAYMENT_TYPES)}")
        stmt = stmt.where(Payment.payment_type.in_(payment_types))

    statuses = csv_arg("status")
    if statuses:
        stmt = stmt.where(Payment.status.in_(statuses))

    providers = csv_arg("provider")
    if providers:
        stmt = stmt.where(Payment.provider.in_(providers))

    q = request.args.get("q")
    if q:
        like = f"%{q}%"

        # Membership side: Member -> Membership -> MembershipPeriod -> PaymentAllocation.
        matching_member_ids = [m.id for m in Member.query.filter(
            or_(Member.name.ilike(like), Member.email.ilike(like))
        ).all()]
        matching_membership_ids = [
            m.id for m in Membership.query.filter(Membership.member_id.in_(matching_member_ids)).all()
        ]
        matching_period_ids = [
            p.id for p in MembershipPeriod.query.filter(
                MembershipPeriod.membership_id.in_(matching_membership_ids)
            ).all()
        ]
        matching_membership_payment_ids = [
            a.payment_id for a in PaymentAllocation.query.filter(
                PaymentAllocation.membership_period_id.in_(matching_period_ids)
            ).all()
        ]

        # Ticket side: an event_ticket Payment's payer only exists via its Order, which
        # PaymentAllocation never touches — searched separately here so a ticket buyer's
        # name/email matches too, not just membership payers.
        matching_order_ids = [
            o.id for o in Order.query.filter(
                or_(Order.customer_name.ilike(like), Order.customer_email.ilike(like))
            ).all()
        ]
        matching_ticket_payment_ids = (
            [p.id for p in Payment.query.filter(Payment.order_id.in_(matching_order_ids)).all()]
            if matching_order_ids
            else []
        )

        matching_reference_payment_ids = [
            p.id for p in Payment.query.filter(Payment.payment_reference.ilike(like)).all()
        ]

        stmt = stmt.where(
            Payment.id.in_(
                matching_membership_payment_ids
                + matching_ticket_payment_ids
                + matching_reference_payment_ids
            )
        )
    return stmt


@admin_payments_bp.get("")
def admin_list_payments():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    try:
        stmt = _filtered_payments_stmt()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_payment_admin(p) for p in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_payments_bp.get("/export")
def admin_export_payments():
    try:
        payments = db.session.scalars(_filtered_payments_stmt()).all()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    order_numbers = {o.id: o.order_number for o in Order.query.all()}

    headers = [
        "Reference", "Type", "Payer", "Order number", "Provider", "Provider transaction ID",
        f"Amount ({site_currency()})", "Currency", "Status", "Periods", "Paid at", "Created at",
    ]
    rows = []
    for payment in payments:
        serialized = _serialize_payment_admin(payment)
        rows.append(
            [
                serialized["payment_reference"],
                serialized["payment_type"],
                serialized["payer_name"],
                order_numbers.get(payment.order_id),
                payment.provider,
                payment.provider_transaction_id,
                payment.amount / 100,
                payment.currency,
                payment.status,
                ", ".join(a["label"] for a in serialized["allocations"]) or None,
                serialized["paid_at"],
                serialized["created_at"],
            ]
        )

    data = write_xlsx(headers, rows)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=payments.xlsx"},
    )


def _pending_membership_payment(payment_id: int):
    payment = db.session.get(Payment, payment_id)
    if payment is None:
        return None, (jsonify({"error": "Payment not found"}), 404)
    if payment.payment_type != "membership" or payment.status != "pending":
        return None, (jsonify({"error": "Only a pending membership payment can be confirmed or rejected."}), 400)
    return payment, None


@admin_payments_bp.post("/<int:payment_id>/confirm")
def admin_confirm_payment(payment_id: int):
    payment, error = _pending_membership_payment(payment_id)
    if error:
        return error
    now = datetime.now(timezone.utc)
    payment.status = "paid"
    payment.paid_at = now
    snapshot_processing_fee(payment)
    paid_periods = []
    for allocation in PaymentAllocation.query.filter_by(payment_id=payment.id).all():
        period = db.session.get(MembershipPeriod, allocation.membership_period_id)
        if period is not None:
            period.status = "paid"
            period.paid_at = now
            paid_periods.append(period)
    db.session.commit()
    # A member's first payment on a self-service request activates that membership.
    activate_pending_memberships_after_payment(paid_periods)
    log_action(
        g.current_user, "payment_confirmed",
        f"Confirmed membership payment {payment.payment_reference or payment.id}",
        target_type="payment", target_id=payment.id,
    )
    return jsonify(_serialize_payment_admin(payment))


@admin_payments_bp.post("/<int:payment_id>/reject")
def admin_reject_payment(payment_id: int):
    payment, error = _pending_membership_payment(payment_id)
    if error:
        return error
    payment.status = "cancelled"  # periods stay unpaid; the member can report again
    db.session.commit()
    log_action(
        g.current_user, "payment_rejected",
        f"Rejected membership payment {payment.payment_reference or payment.id}",
        target_type="payment", target_id=payment.id,
    )
    return jsonify(_serialize_payment_admin(payment))


TEST_PAYMENT_AMOUNT = 100  # øre = 1 kr; the app-payment fee is added on top, like a real payment


@admin_payments_bp.get("/vipps-status")
def admin_vipps_status():
    """Drives the admin page: the test button shows only while configured and not yet public."""
    return jsonify({"configured": vipps.is_enabled(), "public": vipps.is_public()})


@admin_payments_bp.post("/vipps-test")
def admin_start_vipps_test_payment():
    """Admin-only 1 kr payment through the real Vipps App flow, to prove production end to end
    (redirect, confirmation, sweep, refund) before "Vipps App" is switched on for customers.
    Works with credentials alone — it does not need VIPPS_APP_PUBLIC. Has no order or period,
    so confirming it just captures the money and marks the Payment paid."""
    if not vipps.is_enabled():
        return jsonify({"error": "Vipps credentials are not configured."}), 503
    if vipps.is_public():
        return jsonify({"error": "Vipps App is already live for customers; the test payment is retired."}), 409
    surcharge = convenience_fee_for(vipps.PROVIDER, TEST_PAYMENT_AMOUNT)
    payment = Payment(
        payment_type="vipps_test", provider=vipps.PROVIDER,
        amount=TEST_PAYMENT_AMOUNT + surcharge, surcharge_amount=surcharge or None,
        currency="NOK", status="initiated",
    )
    db.session.add(payment)
    db.session.flush()
    payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
    payment.provider_transaction_id = vipps.new_vipps_reference(payment)
    try:
        created = vipps.VippsClient().create_payment(
            payment.provider_transaction_id,
            payment.amount,
            f"{frontend_base_url()}/orders/vipps-return?ref={payment.provider_transaction_id}",
            f"{site_name()} Vipps test payment",
        )
        redirect_url = created.get("redirectUrl")
        if not redirect_url:
            raise vipps.VippsError("Vipps did not return a redirect URL")
    except vipps.VippsError:
        db.session.rollback()
        return jsonify({"error": "Could not start the Vipps payment. Please try again."}), 502
    db.session.commit()
    return jsonify({"payment": _serialize_payment_admin(payment), "redirect_url": redirect_url}), 201


@admin_payments_bp.post("/<int:payment_id>/vipps-check")
def admin_vipps_check(payment_id: int):
    """Manual backstop: re-check a Vipps app payment with Vipps right now."""
    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.provider not in gateway.ONLINE_PROVIDERS:
        return jsonify({"error": "Not an online payment"}), 404
    try:
        gateway.sync(payment)
    except GatewayError:
        db.session.rollback()
        return jsonify({"error": "Could not reach the payment provider. Please try again."}), 502
    return jsonify(_serialize_payment_admin(payment))


@admin_payments_bp.post("/<int:payment_id>/refund")
def admin_refund_payment(payment_id: int):
    payment = db.session.get(Payment, payment_id)
    if payment is None:
        return jsonify({"error": "Payment not found"}), 404
    if payment.status != "paid":
        return jsonify({"error": "Only a paid payment can be refunded."}), 400

    blocked = _refund_block_reason(payment)
    if blocked:
        return jsonify({"error": blocked}), 400

    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()

    if payment.provider in gateway.ONLINE_PROVIDERS and payment.provider_transaction_id:
        # Refund the customer at the provider first (Vipps or Stripe); only flip our own state if that succeeded.
        try:
            gateway.client_for(payment.provider).refund(payment.provider_transaction_id, payment.amount)
        except GatewayError:
            return jsonify({"error": f"{gateway.PROVIDER_NAMES[payment.provider]} could not process the refund. Nothing was changed."}), 502

    payment.status = "refunded"

    cancelled_order = None
    refunded_order = None
    if payment.payment_type == "event_ticket" and payment.order_id is not None:
        order = db.session.get(Order, payment.order_id)
        if order is not None and order.payment_status == "paid":
            # A refunded ticket order is cancelled: its still-valid tickets stop working at the
            # door (same effect as the admin "cancel order" action).
            for item in order.items:
                for ticket in item.tickets:
                    if ticket.status == "valid":
                        ticket.status = "void"
            order.payment_status = "cancelled"
            order.order_status = "cancelled"
            order.cancelled_by_user_id = g.current_user.id
            order.cancelled_at = datetime.now(timezone.utc)
            order.cancellation_reason = f"Payment refunded{': ' + reason if reason else ''}"
            cancelled_order = order.order_number
            refunded_order = order

    if payment.payment_type == "event_donation":
        from app.accounting.models import EventContribution

        donation = EventContribution.query.filter_by(payment_id=payment.id).first()
        if donation is not None:
            donation.status = "refunded"

    if payment.payment_type == "membership":
        allocations = PaymentAllocation.query.filter_by(payment_id=payment.id).all()
        for allocation in allocations:
            period = db.session.get(MembershipPeriod, allocation.membership_period_id)
            if period is not None:
                period.status = "unpaid"
                period.paid_at = None

    db.session.commit()

    description = f"Refunded payment {payment.payment_reference or payment.id}"
    if cancelled_order:
        description += f" (order {cancelled_order} cancelled, tickets voided)"
    if reason:
        description += f" — {reason}"
    log_action(
        g.current_user, "payment_refunded", description,
        target_type="payment", target_id=payment.id,
    )

    if refunded_order is not None:
        # The customer's tickets just stopped working and their money is on its way back: tell them.
        send_order_refunded_email(refunded_order, payment.amount, reason)

    return jsonify(_serialize_payment_admin(payment))
