from datetime import date

from flask import Blueprint, g, jsonify, request

from app.auth.decorators import require_auth
from app.extensions import db
from app.members.routes import find_my_member
from app.memberships.service import (
    discard_pending_request,
    generate_periods_for_membership,
    has_live_payment,
    is_child_type,
)
from app.memberships.models import Membership, MembershipType

memberships_bp = Blueprint("memberships", __name__, url_prefix="/api/memberships")

# membership_type is no longer a hardcoded set — see MembershipType, an admin-editable table
# (app/memberships/admin_routes.py) that replaced it so a non-technical admin can add/reprice
# a type without a code change. Statuses stay hardcoded: they're a fixed lifecycle, not a rate.
VALID_MEMBERSHIP_STATUSES = {"pending", "active", "expired", "cancelled", "suspended"}
# Billing cadence is a fixed, small enumeration (like status above) — not something an admin
# needs to invent new values for, so it stays hardcoded rather than getting its own table.
VALID_BILLING_FREQUENCIES = {"monthly", "quarterly", "yearly"}


def _active_membership_type_names() -> set[str]:
    return {t.name for t in MembershipType.query.filter_by(is_active=True).all()}


def _serialize_membership_type_raw(membership_type: MembershipType) -> dict:
    """Always includes the real price — used by the admin serializer (app/memberships/
    admin_routes.py), which manages the price even while it's hidden from members/the public.
    See _serialize_membership_type below for the public-facing variant.
    """
    return {
        "name": membership_type.name,
        "price": membership_type.price,
        "billing_frequency": membership_type.billing_frequency,
        "contact_for_price": membership_type.contact_for_price,
        "description": membership_type.description,
    }


def _serialize_membership_type(membership_type: MembershipType) -> dict:
    data = _serialize_membership_type_raw(membership_type)
    if membership_type.contact_for_price:
        # Never expose the real price when contact_for_price is on — the frontend renders
        # "Contact us for pricing" instead, so a stale/negotiated number is never shown.
        data["price"] = None
    return data


@memberships_bp.get("/types")
def list_membership_types():
    """Public — powers both the marketing /membership page and the self-service renewal
    dropdown. Only active types are offered; a deactivated type stays valid on any Membership
    row that already references it, it's just no longer selectable for a new one.
    """
    types = (
        MembershipType.query.filter_by(is_active=True)
        .order_by(MembershipType.sort_order, MembershipType.name)
        .all()
    )
    return jsonify({"items": [_serialize_membership_type(t) for t in types]})


def _serialize_membership(membership: Membership) -> dict:
    return {
        "id": membership.id,
        "membership_type": membership.membership_type,
        "status": membership.status,
        "start_date": membership.start_date.isoformat(),
        "end_date": membership.end_date.isoformat() if membership.end_date else None,
    }


@memberships_bp.get("/me")
@require_auth
def list_my_memberships():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"items": []})

    memberships = (
        Membership.query.filter_by(member_id=member.id)
        .order_by(Membership.start_date.desc())
        .all()
    )
    return jsonify({"items": [_serialize_membership(m) for m in memberships]})


@memberships_bp.delete("/me/request")
@require_auth
def cancel_my_request():
    """The member changes their mind before paying: removes their own pending request (and its
    unpaid periods). Refused once a payment has been reported or started — money may be on its
    way, so an admin handles it from there."""
    member = find_my_member(g.current_user)
    pending = (
        Membership.query.filter_by(member_id=member.id, status="pending").first() if member else None
    )
    if pending is None:
        return jsonify({"error": "You have no pending membership request."}), 404
    if has_live_payment(pending):
        return jsonify(
            {"error": "A payment has already been reported for this request. Please contact us to change it."}
        ), 409
    discard_pending_request(pending)
    db.session.commit()
    return "", 204


@memberships_bp.post("/me")
@require_auth
def request_renewal():
    """Self-service membership renewal request. Never trusts a client-supplied member_id or
    start_date — always resolves "me" from the authenticated user and stamps today's date.
    Creates a `status="pending"` row plus its billing periods; the member then pays the current
    period (payment_routes.py) and the membership activates automatically once that is
    confirmed. A type with no price has no periods and is still approved by an admin
    (`PATCH /api/admin/memberships/<id>`).
    """
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"error": "Complete your member profile before requesting membership."}), 400

    data = request.get_json(silent=True) or {}
    membership_type = data.get("membership_type")
    valid_types = _active_membership_type_names()
    if membership_type not in valid_types:
        return jsonify(
            {"errors": {"membership_type": f"Must be one of {sorted(valid_types)}."}}
        ), 400

    if is_child_type(membership_type) and member.parent_member_id is None:
        return jsonify(
            {"errors": {"membership_type": "A child membership must be arranged by an admin or volunteer."}}
        ), 400

    existing_active = Membership.query.filter_by(member_id=member.id, status="active").first()
    if existing_active is not None:
        return jsonify({"error": "You already have an active or pending membership."}), 409

    # A pending request nobody has paid for yet can be swapped for another type; once a payment
    # has been started or reported it is locked (the admin handles it from there).
    existing_pending = Membership.query.filter_by(member_id=member.id, status="pending").first()
    if existing_pending is not None:
        if has_live_payment(existing_pending):
            return jsonify(
                {"error": "You already have an active or pending membership."}
            ), 409
        discard_pending_request(existing_pending)

    membership = Membership(
        member_id=member.id,
        membership_type=membership_type,
        status="pending",
        start_date=date.today(),
    )
    db.session.add(membership)
    db.session.commit()
    # Periods now (not at approval), so the member can pay the current one straight away; a
    # contact-for-price type has none and stays an ordinary request for an admin to approve.
    generate_periods_for_membership(membership)

    return jsonify(_serialize_membership(membership)), 201
