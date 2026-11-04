"""Admin side of the Donations module: list, confirm receipt, reject, export. Admin only."""

from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.donations.emails import send_donation_receipt_email
from app.donations.models import Donation
from app.extensions import db
from app.imports.excel import write_xlsx
from app.payments import gateway
from app.payments.errors import GatewayError
from app.payments.methods import BANK, CASH, VIPPS_QR
from app.payments.models import Payment

admin_donations_bp = Blueprint("admin_donations", __name__, url_prefix="/api/admin/donations")
admin_donations_bp.before_request(require_role("admin"))

STATUSES = ("pending", "pending_verification", "paid", "rejected", "cancelled")
MAX_PER_PAGE = 50


def _latest_payment(donation: Donation) -> Payment | None:
    return Payment.query.filter_by(donation_id=donation.id).order_by(Payment.created_at.desc()).first()


def _serialize(donation: Donation) -> dict:
    payment = _latest_payment(donation)
    return {
        "id": donation.id,
        "reference": donation.reference,
        "donor_name": donation.donor_name,
        "donor_email": donation.donor_email,
        "anonymous": donation.anonymous,
        "message": donation.message,
        "amount": donation.amount,
        "currency": donation.currency,
        "status": donation.status,
        "payment_method": payment.provider if payment else None,
        "created_at": donation.created_at.isoformat(),
        "paid_at": donation.paid_at.isoformat() if donation.paid_at else None,
    }


def _filtered():
    query = Donation.query
    status = request.args.get("status")
    if status:
        query = query.filter(Donation.status == status)
    text = (request.args.get("q") or "").strip()
    if text:
        like = f"%{text}%"
        query = query.filter(or_(Donation.donor_name.ilike(like), Donation.donor_email.ilike(like), Donation.reference.ilike(like)))
    return query.order_by(Donation.created_at.desc(), Donation.id.desc())


@admin_donations_bp.get("")
def admin_list_donations():
    status = request.args.get("status")
    if status and status not in STATUSES:
        return jsonify({"errors": {"status": f"Must be one of {', '.join(STATUSES)}."}}), 400
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 25, type=int), 1), MAX_PER_PAGE)
    query = _filtered()
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    paid_total = sum(d.amount for d in Donation.query.filter_by(status="paid").all())
    return jsonify({"items": [_serialize(d) for d in rows], "total": total, "page": page, "per_page": per_page, "paid_total": paid_total})


@admin_donations_bp.get("/export")
def admin_export_donations():
    rows = [
        [
            d.reference,
            d.created_at.date().isoformat(),
            d.donor_name,
            d.donor_email,
            "yes" if d.anonymous else "",
            d.amount / 100,
            d.currency,
            d.status,
            (_latest_payment(d).provider if _latest_payment(d) else ""),
            d.paid_at.date().isoformat() if d.paid_at else "",
            d.message or "",
        ]
        for d in _filtered().all()
    ]
    data = write_xlsx(
        ["Reference", "Date", "Name", "Email", "Anonymous", "Amount", "Currency", "Status", "Method", "Paid on", "Message"], rows
    )
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=donations.xlsx"},
    )


def _release_vipps_attempt(payment: Payment | None) -> None:
    """Best effort: an open online attempt (Vipps app or Stripe card) has charged nothing yet, so cancelling it is always safe."""
    if payment is not None and payment.provider in gateway.ONLINE_PROVIDERS and payment.status == "initiated":
        payment.status = "cancelled"
        if payment.provider_transaction_id:
            try:
                gateway.client_for(payment.provider).cancel(payment.provider_transaction_id)
            except (GatewayError, KeyError):
                pass


@admin_donations_bp.post("/<int:donation_id>/mark-paid")
def admin_mark_paid(donation_id: int):
    donation = db.session.get(Donation, donation_id)
    if donation is None:
        return jsonify({"error": "Donation not found"}), 404
    if donation.status == "paid":
        return jsonify(_serialize(donation))  # idempotent
    if donation.status not in ("pending", "pending_verification"):
        return jsonify({"error": "Only unpaid donations can be marked as paid."}), 409

    paid_with = (request.get_json(silent=True) or {}).get("payment_method")
    if paid_with not in (None, CASH, VIPPS_QR, BANK):
        return jsonify({"errors": {"payment_method": "Must be cash, vipps_qr or bank_transfer."}}), 400
    payment = _latest_payment(donation)
    if payment is not None and payment.provider in gateway.ONLINE_PROVIDERS:
        _release_vipps_attempt(payment)  # settled another way: the online attempt (Vipps or card) must never also charge
        payment = None
    now = datetime.now(timezone.utc)
    if payment is not None:
        if paid_with:
            payment.provider = paid_with
        payment.status = "paid"
        payment.paid_at = now
    donation.status = "paid"
    donation.paid_at = now
    donation.confirmed_by_user_id = g.current_user.id
    db.session.commit()
    log_action(g.current_user, "donation.marked_paid", f"Marked donation {donation.reference} as paid", target_type="donation", target_id=donation.id)
    send_donation_receipt_email(donation)
    return jsonify(_serialize(donation))


@admin_donations_bp.post("/<int:donation_id>/reject")
def admin_reject(donation_id: int):
    donation = db.session.get(Donation, donation_id)
    if donation is None:
        return jsonify({"error": "Donation not found"}), 404
    if donation.status == "rejected":
        return jsonify(_serialize(donation))
    if donation.status not in ("pending", "pending_verification"):
        return jsonify({"error": "Only unpaid donations can be rejected."}), 409
    for payment in Payment.query.filter_by(donation_id=donation.id, status="initiated").all():
        _release_vipps_attempt(payment)
    donation.status = "rejected"
    db.session.commit()
    log_action(g.current_user, "donation.rejected", f"Rejected donation {donation.reference}", target_type="donation", target_id=donation.id)
    return jsonify(_serialize(donation))
