from flask import Blueprint, jsonify, request

from app.auth.optional import optional_admin_user
from app.coupons.models import Coupon, redemption_count_for_coupon
from app.events.models import Event
from app.extensions import db

coupons_bp = Blueprint("coupons", __name__, url_prefix="/api/coupons")


@coupons_bp.get("/validate")
def validate_coupon():
    """Public, read-only preview for the checkout page — never creates or charges anything.
    Checkout (app/orders/routes.py) re-validates and re-computes the discount server-side
    regardless of what this returned, so this endpoint is purely a UX convenience.
    """
    event_id = request.args.get("event_id")
    code = (request.args.get("code") or "").strip()
    if not event_id or not code:
        return jsonify({"valid": False, "error": "event_id and code are required"}), 400
    try:
        event_id = int(event_id)
    except ValueError:
        return jsonify({"valid": False, "error": "event_id must be an integer"}), 400

    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"valid": False, "error": "Coupon not found"}), 404
    # An admin's own authenticated request can also preview a coupon for a draft event — see the
    # matching note on app.events.routes.get_event.
    if not event.published and optional_admin_user() is None:
        return jsonify({"valid": False, "error": "Coupon not found"}), 404

    coupon = Coupon.query.filter_by(event_id=event_id, code=code.upper(), is_active=True).first()
    if coupon is None:
        return jsonify({"valid": False, "error": "Invalid or inactive coupon code."})

    remaining_redemptions = None
    if coupon.max_redemptions is not None:
        remaining_redemptions = max(coupon.max_redemptions - redemption_count_for_coupon(coupon.id), 0)

    return jsonify(
        {
            "valid": True,
            "code": coupon.code,
            "discount_percent": coupon.discount_percent,
            # Empty means unrestricted (applies to any coupon-eligible ticket type) — see
            # Coupon.applies_to_ticket_type(). Exposed so the checkout page's discount preview
            # can match the backend's own per-coupon restriction rather than assuming every
            # coupon-eligible item is discounted.
            "allowed_ticket_type_ids": coupon.allowed_ticket_type_id_list(),
            # null means unlimited. Otherwise, how many more TICKETS this coupon can be used for
            # right now (see Coupon.max_redemptions' own docstring) — lets the checkout preview
            # warn before submit rather than only after checkout's own hard gate rejects it.
            "remaining_redemptions": remaining_redemptions,
        }
    )
