"""Public "become a member" form on /membership — a guest picks a type, enters name/email (a child:
the parent's email) and pays, with no account. Same shape as the Membership Drive signup, but the
person pays for themselves, so nothing is active until the payment is confirmed: the membership is
created `pending` with its periods, and activates through the normal path once the current period
is paid (admin confirms a Vipps-QR payment, or Vipps confirms a Vipps-App one). "Pay later" just
leaves the pending request, which they can pay from the dashboard after signing in with the same
email (find_my_member links it). A type with no price (e.g. Lifetime) has nothing to pay, so it is
left as an ordinary pending request for an admin to approve.
"""

import re
from datetime import date

from flask import Blueprint, jsonify, request

from app.common.phone import is_valid_phone
from app.common.site import site_currency, site_name, site_phone_rule
from app.common.urls import frontend_base_url
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipType
from app.memberships.service import (
    current_period_for_date,
    discard_pending_request,
    ensure_family_entry_for_child,
    find_member_by_email,
    generate_periods_for_membership,
    has_live_payment,
    is_child_type,
    parent_adult_error,
)
from app.payments import gateway, stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.fees import convenience_fee_for, convenience_percent
from app.payments.methods import STRIPE, VIPPS_QR
from app.payments.models import Payment, PaymentAllocation
from app.settings.models import get_site_settings

membership_join_bp = Blueprint("membership_join", __name__, url_prefix="/api/memberships/join")

PAY_LATER = "pay_later"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def available_methods() -> list[str]:
    methods = []
    if vipps.is_public():
        methods.append(vipps.PROVIDER)
    if stripe_gateway.is_public():
        methods.append(STRIPE)
    if get_site_settings().vipps_qr_enabled:
        methods.append(VIPPS_QR)
    methods.append(PAY_LATER)
    return methods


@membership_join_bp.get("/options")
def options():
    methods = available_methods()
    fees = {m: float(convenience_percent(m)) for m in methods if m != PAY_LATER}
    return jsonify({"payment_methods": methods, "convenience_percent": fees})


@membership_join_bp.post("")
def join():
    data = request.get_json(silent=True) or {}
    type_name = data.get("membership_type")
    membership_type = (
        MembershipType.query.filter_by(name=type_name, is_active=True).first()
        if isinstance(type_name, str)
        else None
    )
    is_child = is_child_type(type_name)

    errors: dict[str, str] = {}
    if membership_type is None:
        errors["membership_type"] = "Choose a membership type."
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "This field is required."
    email_field = "parent_email" if is_child else "email"
    email = data.get(email_field)
    if not isinstance(email, str) or not email.strip():
        errors[email_field] = "This field is required."
    elif not EMAIL_RE.match(email.strip()):
        errors[email_field] = "Enter a valid email address."
    phone = data.get("phone")
    phone = phone.strip() if isinstance(phone, str) else ""
    if phone and not is_valid_phone(phone, site_phone_rule()):
        errors["phone"] = site_phone_rule().message()

    method = data.get("payment_method") or PAY_LATER
    if method not in available_methods():
        errors["payment_method"] = "That payment method is not available."

    parent = None
    if is_child and email_field not in errors:
        parent = find_member_by_email(email)
        parent_error = parent_adult_error(parent)
        if parent_error:
            errors["parent_email"] = parent_error
    if errors:
        return jsonify({"errors": errors}), 400

    email = email.strip()
    if is_child:
        member = Member(name=name.strip(), phone=phone or None, parent_member_id=parent.id)
        db.session.add(member)
        db.session.flush()
        ensure_family_entry_for_child(member)
    else:
        member = find_member_by_email(email)
        if member is not None and Membership.query.filter_by(member_id=member.id, status="active").first():
            return jsonify({"errors": {"email": "This email already has an active membership. Log in to renew."}}), 409
        if member is None:
            member = Member(name=name.strip(), email=email, phone=phone or None)
            db.session.add(member)
        db.session.flush()

    pending = Membership.query.filter_by(member_id=member.id, status="pending").first()
    if pending is not None:
        if has_live_payment(pending):
            db.session.rollback()
            return jsonify({"errors": {"email": "A request with a payment in progress already exists for this email."}}), 409
        discard_pending_request(pending)

    membership = Membership(
        member_id=member.id, membership_type=membership_type.name, status="pending", start_date=date.today()
    )
    db.session.add(membership)
    db.session.flush()
    generate_periods_for_membership(membership)
    period = current_period_for_date(membership, date.today())

    payment = None
    redirect_url = None
    if period is not None and method != PAY_LATER:
        # The convenience fee set for this method (Settings -> Payments) is charged on top.
        surcharge = convenience_fee_for(method, period.amount)
        payment = Payment(
            payment_type="membership", provider=method, amount=period.amount + surcharge, currency=site_currency(),
            surcharge_amount=surcharge or None,
            status="initiated" if method in gateway.ONLINE_PROVIDERS else "pending",
        )
        db.session.add(payment)
        db.session.flush()
        payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
        db.session.add(PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=period.amount))
        if method in gateway.ONLINE_PROVIDERS:
            try:
                redirect_url = gateway.start_payment(
                    payment, f"{frontend_base_url()}/orders/vipps-return?ref={{ref}}&kind=membership", f"{site_name()} membership"
                )
            except GatewayError:
                db.session.rollback()
                return jsonify({"error": "Could not start the card payment. Please try again." if method == STRIPE else "Could not start the Vipps payment. Please try again."}), 502

    db.session.commit()
    return (
        jsonify(
            {
                "membership_type": membership.membership_type,
                "payment_method": method if payment else PAY_LATER,
                "payment": (
                    {
                        "id": payment.id,
                        "payment_reference": payment.payment_reference,
                        "amount": payment.amount,
                        "status": payment.status,
                    }
                    if payment
                    else None
                ),
                "redirect_url": redirect_url,
            }
        ),
        201,
    )
