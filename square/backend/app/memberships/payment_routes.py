"""Self-service membership payment endpoints — period listing and starting a payment. Every
route resolves "me" via find_my_member(g.current_user); none accept a member_id or membership_id
from the request.
"""

from flask import Blueprint, g, jsonify, request

from app.common.site import site_name
from app.auth.decorators import require_auth
from app.extensions import db
from app.members.models import Member
from app.members.routes import find_my_member
from datetime import date

from app.memberships.models import Membership, MembershipPeriod, MembershipTypeChange
from app.memberships.service import current_period_for_date
from app.common.site import site_currency
from app.common.urls import frontend_base_url
from app.payments import vipps
from app.payments.bank import bank_details
from app.payments.fees import convenience_fee_for, convenience_percent
from app.payments import gateway, stripe_gateway
from app.payments.errors import GatewayError
from app.payments.methods import BANK, CASH, STRIPE, VIPPS_QR, normalize_method
from app.payments.models import Payment, PaymentAllocation
from app.settings.models import bank_transfer_available, get_site_settings, vipps_qr_available

memberships_payment_bp = Blueprint(
    "memberships_payment", __name__, url_prefix="/api/memberships/me"
)

# Manual Vipps only: the member pays via the static Vipps QR/number and reports it; the payment
# stays "pending" until an admin confirms it (same philosophy as ticket orders).
# "vipps_app" = the real Vipps ePayment API (app/payments/vipps.py): confirmed by Vipps itself,
# charged with a surcharge.
VALID_PROVIDERS = {VIPPS_QR, CASH, BANK, vipps.PROVIDER, STRIPE}


def _pending_period_ids(period_ids: list[int]) -> set[int]:
    """Ids among `period_ids` already covered by a member-reported, not-yet-confirmed payment."""
    if not period_ids:
        return set()
    rows = (
        db.session.query(PaymentAllocation.membership_period_id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.membership_period_id.in_(period_ids),
            Payment.status == "pending",
        )
        .all()
    )
    return {pid for (pid,) in rows}


def _serialize_period(period: MembershipPeriod, pending_ids: set[int] = frozenset()) -> dict:
    return {
        "payment_pending": period.id in pending_ids,
        "id": period.id,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "label": period.label,
        "amount": period.amount,
        "currency": period.currency,
        "status": period.status,
        "paid_at": period.paid_at.isoformat() if period.paid_at else None,
    }


def _current_membership(member) -> Membership | None:
    """The member's active membership; failing that, their pending request IF it already has
    periods (a self-service request waiting for its first payment)."""
    active = (
        Membership.query.filter_by(member_id=member.id, status="active")
        .order_by(Membership.start_date.desc())
        .first()
    )
    if active is not None:
        return active
    for pending in (
        Membership.query.filter_by(member_id=member.id, status="pending")
        .order_by(Membership.start_date.desc())
        .all()
    ):
        if MembershipPeriod.query.filter_by(membership_id=pending.id).first() is not None:
            return pending
    return None


def _payable_member_ids(member) -> list[int]:
    """The member themself plus their children — a parent may pay for a child's membership."""
    child_ids = [cid for (cid,) in db.session.query(Member.id).filter(Member.parent_member_id == member.id).all()]
    return [member.id, *child_ids]


@memberships_payment_bp.get("/children-awaiting")
@require_auth
def list_children_awaiting_payment():
    """Children of the signed-in member whose membership request is waiting for its first payment
    (e.g. saved with "pay later" at the Membership Drive). Each carries the one payable period."""
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"items": []})
    items = []
    children = Member.query.filter_by(parent_member_id=member.id).order_by(Member.name).all()
    for child in children:
        membership = (
            Membership.query.filter_by(member_id=child.id, status="pending")
            .order_by(Membership.start_date.desc())
            .first()
        )
        if membership is None:
            continue
        current = current_period_for_date(membership, date.today())
        if current is None or current.status != "unpaid":
            continue
        items.append(
            {
                "member_id": child.id,
                "name": child.name,
                "membership_type": membership.membership_type,
                "period": _serialize_period(current, _pending_period_ids([current.id])),
            }
        )
    return jsonify(
        {
            "items": items,
            "vipps_app": {"enabled": vipps.is_public(), "surcharge_percent": float(convenience_percent(vipps.PROVIDER))},
            "stripe": {"enabled": stripe_gateway.is_public(), "surcharge_percent": stripe_gateway.surcharge_percent()},
            "cash": {"enabled": bool(get_site_settings().cash_enabled), "note": (get_site_settings().cash_membership_note or "").strip()},
        }
    )


@memberships_payment_bp.get("/periods")
@require_auth
def list_my_periods():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"membership": None, "items": []})

    membership = _current_membership(member)
    if membership is None:
        return jsonify({"membership": None, "items": []})

    periods = (
        MembershipPeriod.query.filter_by(membership_id=membership.id)
        .order_by(MembershipPeriod.period_start)
        .all()
    )
    if membership.status == "pending":
        # Before activation only the current period is payable — show just that one.
        current = current_period_for_date(membership, date.today())
        periods = [current] if current is not None else []
    pending_ids = _pending_period_ids([p.id for p in periods])
    return jsonify(
        {
            "membership": {
                "id": membership.id,
                "membership_type": membership.membership_type,
                "status": membership.status,
            },
            "items": [_serialize_period(p, pending_ids) for p in periods],
            "vipps_app": {"enabled": vipps.is_public(), "surcharge_percent": float(convenience_percent(vipps.PROVIDER))},
            "stripe": {"enabled": stripe_gateway.is_public(), "surcharge_percent": stripe_gateway.surcharge_percent()},
            "cash": {"enabled": bool(get_site_settings().cash_enabled), "note": (get_site_settings().cash_membership_note or "").strip()},
            "bank": {
                "enabled": bank_transfer_available(get_site_settings()),
                "details": bank_details(get_site_settings()) if bank_transfer_available(get_site_settings()) else None,
            },
            "vipps_qr": {
                "enabled": vipps_qr_available(get_site_settings()),
                "number": (get_site_settings().vipps_number or "").strip() or None if vipps_qr_available(get_site_settings()) else None,
                "image_url": get_site_settings().vipps_qr_image_url if vipps_qr_available(get_site_settings()) else None,
            },
            "type_changes": [
                {"from_type": c.from_type, "to_type": c.to_type, "changed_at": c.changed_at.isoformat()}
                for c in MembershipTypeChange.query.filter_by(membership_id=membership.id)
                .order_by(MembershipTypeChange.changed_at)
                .all()
            ],
        }
    )


@memberships_payment_bp.post("/payments")
@require_auth
def start_my_payment():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"error": "Complete your member profile before paying."}), 400

    data = request.get_json(silent=True) or {}
    period_ids = data.get("membership_period_ids")
    provider = normalize_method(data.get("provider"))

    if not isinstance(period_ids, list) or not period_ids or not all(
        isinstance(i, int) for i in period_ids
    ):
        return jsonify({"errors": {"membership_period_ids": "Must be a non-empty list of ids."}}), 400
    if provider not in VALID_PROVIDERS:
        return jsonify({"errors": {"provider": f"Must be one of {sorted(VALID_PROVIDERS)}."}}), 400
    if provider == CASH and not get_site_settings().cash_enabled:
        return jsonify({"errors": {"provider": "Cash payment is not available right now."}}), 400
    if provider == VIPPS_QR and not vipps_qr_available(get_site_settings()):
        return jsonify({"errors": {"provider": "Vipps-QR payment is not available right now."}}), 400
    if provider == BANK and not bank_transfer_available(get_site_settings()):
        return jsonify({"errors": {"provider": "Bank transfer is not available right now."}}), 400

    periods = (
        MembershipPeriod.query.join(Membership, MembershipPeriod.membership_id == Membership.id)
        .filter(
            MembershipPeriod.id.in_(period_ids),
            Membership.member_id.in_(_payable_member_ids(member)),
        )
        .with_for_update(of=MembershipPeriod)
        .all()
    )
    if len(periods) != len(set(period_ids)):
        return jsonify({"error": "One or more periods not found."}), 400
    for period in periods:
        owner = db.session.get(Membership, period.membership_id)
        if owner is not None and owner.status == "pending":
            current = current_period_for_date(owner, date.today())
            if current is None or period.id != current.id:
                return jsonify(
                    {"error": "Only the current period can be paid before your membership is active."}
                ), 400
    if any(p.status != "unpaid" for p in periods):
        return jsonify({"error": "One or more periods are already paid."}), 400
    if _pending_period_ids([p.id for p in periods]):
        return jsonify({"error": "A payment for one or more periods is already awaiting confirmation."}), 400

    base_total = sum(p.amount for p in periods)
    surcharge = 0
    online = provider in gateway.ONLINE_PROVIDERS
    if online:
        if not gateway.is_public(provider):
            return jsonify({"error": "Card payment is not available right now." if provider == STRIPE else "Vipps app payment is not available right now."}), 503
        surcharge = convenience_fee_for(provider, base_total)

    payment = Payment(
        payment_type="membership", provider=provider, amount=base_total + surcharge, currency=site_currency(),
        surcharge_amount=surcharge or None,
        status="initiated" if online else "pending",
    )
    db.session.add(payment)
    db.session.flush()
    payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"

    for period in periods:
        db.session.add(
            PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=period.amount)
        )

    redirect_url = None
    if online:
        try:
            _cancel_stale_initiated([p.id for p in periods], payment.id)
            redirect_url = gateway.start_payment(payment, f"{frontend_base_url()}/member?vipps_payment={payment.id}", f"{site_name()} membership")
        except GatewayError:
            db.session.rollback()
            return jsonify({"error": "Could not start the card payment. Please try again." if provider == STRIPE else "Could not start the Vipps payment. Please try again."}), 502

    db.session.commit()

    return jsonify(
        {
            "payment": {
                "id": payment.id,
                "payment_reference": payment.payment_reference,
                "amount": payment.amount,
                "surcharge_amount": payment.surcharge_amount or 0,
                "status": payment.status,
            },
            "redirect_url": redirect_url,
        }
    )


def _cancel_stale_initiated(period_ids: list[int], keep_payment_id: int) -> None:
    """A member who abandons the Vipps page and tries again leaves an "initiated" payment behind.
    Cancel those (best effort at Vipps — nothing was charged) so two live payments never cover
    the same period."""
    stale = (
        Payment.query.join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.membership_period_id.in_(period_ids),
            Payment.provider.in_(gateway.ONLINE_PROVIDERS),
            Payment.status == "initiated",
            Payment.id != keep_payment_id,
        )
        .distinct()
        .all()
    )
    for old in stale:
        old.status = "cancelled"
        if old.provider_transaction_id:
            try:
                gateway.client_for(old.provider).cancel(old.provider_transaction_id)
            except GatewayError:
                pass


@memberships_payment_bp.post("/payments/<int:payment_id>/refresh")
@require_auth
def refresh_my_payment(payment_id: int):
    """Called by the dashboard when the customer returns from Vipps. Asks Vipps for the real
    state (never trusts the browser) and returns the payment's resulting status."""
    member = find_my_member(g.current_user)
    payment = (
        Payment.query.join(PaymentAllocation, PaymentAllocation.payment_id == Payment.id)
        .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
        .join(Membership, MembershipPeriod.membership_id == Membership.id)
        .filter(
            Payment.id == payment_id,
            Payment.provider.in_(gateway.ONLINE_PROVIDERS),
            Membership.member_id.in_(_payable_member_ids(member) if member else [-1]),
        )
        .first()
    )
    if payment is None:
        return jsonify({"error": "Payment not found"}), 404
    try:
        payment = gateway.sync(payment)
    except GatewayError:
        return jsonify({"error": "Could not check the payment with the payment provider. Please try again."}), 502
    return jsonify({"payment": {"id": payment.id, "status": payment.status}})


@memberships_payment_bp.get("/payments")
@require_auth
def list_my_membership_payments():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"items": []})

    payment_ids = (
        db.session.query(PaymentAllocation.payment_id)
        .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
        .join(Membership, MembershipPeriod.membership_id == Membership.id)
        .filter(Membership.member_id.in_(_payable_member_ids(member)))
        .distinct()
        .all()
    )
    payment_ids = [pid for (pid,) in payment_ids]

    payments = (
        Payment.query.filter(Payment.id.in_(payment_ids))
        .order_by(Payment.created_at.desc())
        .all()
        if payment_ids
        else []
    )

    items = []
    for payment in payments:
        allocations = (
            PaymentAllocation.query.filter_by(payment_id=payment.id)
            .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
            .add_columns(MembershipPeriod.label)
            .all()
        )
        items.append(
            {
                "id": payment.id,
                "payment_reference": payment.payment_reference,
                "provider": payment.provider,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "created_at": payment.created_at.isoformat(),
                "allocations": [
                    {"amount": allocation.amount, "label": label}
                    for allocation, label in allocations
                ],
            }
        )

    return jsonify({"items": items})
