"""Membership Drive — a volunteer-facing, in-person membership signup/renewal flow: pick a
type, enter the person's name/email/phone, tap "Mark as paid" and the membership activates
immediately with no pending/review step (a festival-table signup collects payment in person,
on the spot — there's nothing left to verify asynchronously the way an online self-service
payment would need). Protected by admin OR volunteer — a narrower, purpose-built surface, same
precedent as app/checkin/admin_routes.py, not admin-only like the rest of
app/memberships/admin_routes.py.

Only the ONE period covering today gets charged (this month for a monthly type, this quarter
for quarterly, the year for yearly) — matching the type's own normal billing cadence rather than
collecting the whole year upfront. Any later period stays unpaid, payable by the member
themselves later via the existing self-service flow at /member. A contact_for_price type (e.g.
Lifetime) has no periods at all, so no payment is recorded — the membership still activates.

Because Member.user_id stays null until first login (see find_my_member), a person signed up
here shows their new membership as active the moment they later log in with the same email —
no extra code needed for that part.
"""

import re
from datetime import date

from flask import Blueprint, g, jsonify, request
from app.common.phone import is_valid_phone
from app.common.site import site_phone_rule
from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.members.models import Member
from app.memberships.emails import send_membership_active_email
from app.memberships.models import Membership, MembershipType
from app.memberships.routes import _serialize_membership
from app.memberships.service import (
    complete_membership_payment_immediately,
    discard_pending_request,
    generate_periods_for_membership,
    has_live_payment,
    is_child_type,
    current_period_for_date,
    ensure_family_entry_for_child,
    find_member_by_email,
    activate_membership,
    parent_adult_error,
)
from app.payments.methods import CASH, VIPPS_QR

# "Will pay later": the signup is saved as a pending request awaiting payment (no payment recorded).
PAY_LATER = "pay_later"
from app.settings.models import get_site_settings

membership_drive_bp = Blueprint(
    "membership_drive", __name__, url_prefix="/api/admin/membership-drive"
)
membership_drive_bp.before_request(require_role("admin", "volunteer"))

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@membership_drive_bp.get("/options")
def options():
    """What the volunteer's pay step may offer: Vipps-QR always, Cash while an admin has it switched on."""
    return jsonify({"cash_enabled": bool(get_site_settings().cash_enabled)})


def _is_contact_for_price(type_name: str) -> bool:
    membership_type = db.session.get(MembershipType, type_name)
    return membership_type is None or bool(membership_type.contact_for_price)


@membership_drive_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}

    membership_type_name = data.get("membership_type")
    valid_types = {t.name for t in MembershipType.query.filter_by(is_active=True).all()}
    is_child = is_child_type(membership_type_name)

    errors: dict[str, str] = {}
    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        errors["name"] = "This field is required."
    # A child has no email/login of their own — the parent's email (below) identifies the link.
    email_field = "parent_email" if is_child else "email"
    email = data.get(email_field)
    if not email or not isinstance(email, str) or not email.strip():
        errors[email_field] = "This field is required."
    elif not EMAIL_RE.match(email.strip()):
        errors[email_field] = "Enter a valid email address."
    # Phone is optional at the drive (people new to the country may not have one yet); when given it
    # must still be a valid Norwegian mobile.
    phone = data.get("phone")
    if phone is not None and not isinstance(phone, str):
        errors["phone"] = site_phone_rule().message()
    else:
        phone = (phone or "").strip()
        if phone and not is_valid_phone(phone, site_phone_rule()):
            errors["phone"] = site_phone_rule().message()

    if membership_type_name not in valid_types:
        errors["membership_type"] = f"Must be one of {sorted(valid_types)}."

    parent = None
    if is_child and email_field not in errors:
        parent = find_member_by_email(email)
        parent_error = parent_adult_error(parent)
        if parent_error:
            errors["parent_email"] = parent_error

    paid_with = data.get("payment_method") or VIPPS_QR
    if paid_with not in (VIPPS_QR, CASH, PAY_LATER):
        errors["payment_method"] = "Must be cash, vipps_qr or pay_later."
    elif paid_with == CASH and not get_site_settings().cash_enabled:
        errors["payment_method"] = "Cash is not switched on in Settings → Payments."

    if errors:
        return jsonify({"errors": errors}), 400

    if is_child:
        # Always a new Member — a child has no email to find an existing record by.
        member = Member(
            name=name.strip(), phone=(phone or "").strip() or None, parent_member_id=parent.id
        )
        db.session.add(member)
        db.session.flush()
        ensure_family_entry_for_child(member)
        db.session.commit()
    else:
        member = find_member_by_email(email)
        if member is None:
            member = Member(name=name.strip(), email=email.strip(), phone=phone or None)
            db.session.add(member)
            db.session.commit()

    today = date.today()
    # A type with no price has nothing to pay, so "pay later" only applies to a priced type.
    pay_later = paid_with == PAY_LATER and not _is_contact_for_price(membership_type_name)
    if pay_later:
        # Same shape as a self-service request: pending, periods ready, activates by itself when the
        # current period is paid (the member's dashboard, or an admin confirming a manual payment).
        # A pending request nobody has paid for is replaced; one with a payment started is kept.
        existing_pending = Membership.query.filter_by(member_id=member.id, status="pending").first()
        if existing_pending is not None:
            if has_live_payment(existing_pending):
                return jsonify({"errors": {"payment_method": "This member already has a request with a payment in progress."}}), 409
            discard_pending_request(existing_pending)

    membership = Membership(
        member_id=member.id,
        membership_type=membership_type_name,
        status="pending" if pay_later else "active",
        start_date=today,
    )
    db.session.add(membership)
    db.session.commit()

    if pay_later:
        generate_periods_for_membership(membership)
        payment = None
    else:
        activate_membership(membership)
        send_membership_active_email(membership)
        current_period = current_period_for_date(membership, today)
        payment = complete_membership_payment_immediately(
            [current_period] if current_period else [], provider=paid_with
        )

    log_action(
        g.current_user,
        "membership_drive_signup",
        f"Signed up {member.name} ({email.strip()}{' — parent' if is_child else ''}) for {membership_type_name} via the membership drive{' (will pay later)' if pay_later else ''}",
        target_type="membership",
        target_id=membership.id,
    )

    return (
        jsonify(
            {
                "member": {"id": member.id, "name": member.name, "email": None if is_child else email.strip()},
                "membership": _serialize_membership(membership),
                "payment": (
                    {
                        "id": payment.id,
                        "amount": payment.amount,
                        "currency": payment.currency,
                        "status": payment.status,
                    }
                    if payment
                    else None
                ),
            }
        ),
        201,
    )
