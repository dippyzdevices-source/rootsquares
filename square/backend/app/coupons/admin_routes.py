from flask import Blueprint, g, jsonify, request

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.coupons.models import Coupon, redemption_count_for_coupon
from app.extensions import db
from app.tickets.models import TicketType

admin_coupons_bp = Blueprint("admin_coupons", __name__, url_prefix="/api/admin")
admin_coupons_bp.before_request(require_role("admin"))


def _user_email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user else None


def _serialize_coupon_admin(coupon: Coupon) -> dict:
    return {
        "id": coupon.id,
        "event_id": coupon.event_id,
        "code": coupon.code,
        "discount_percent": coupon.discount_percent,
        "is_active": coupon.is_active,
        "allowed_ticket_type_ids": coupon.allowed_ticket_type_id_list(),
        "max_redemptions": coupon.max_redemptions,
        "redemption_count": redemption_count_for_coupon(coupon.id),
        "created_by_email": _user_email(coupon.created_by),
        "updated_by_email": _user_email(coupon.updated_by),
    }


def _validate_coupon_payload(data: dict, event_id: int, existing: Coupon | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        if not data.get("code"):
            errors["code"] = "This field is required."
        if data.get("discount_percent") is None:
            errors["discount_percent"] = "This field is required."

    if "code" in data:
        value = data["code"]
        if not isinstance(value, str) or not value.strip():
            errors["code"] = "Must be a non-empty string."
        elif len(value.strip()) > 50:
            errors["code"] = "Must be at most 50 characters."
        else:
            # Stored/compared upper-cased so "SAVE20" and "save20" are the same code — both
            # here (uniqueness) and at checkout (app/orders/routes.py).
            code = value.strip().upper()
            query = Coupon.query.filter_by(event_id=event_id, code=code)
            if existing is not None:
                query = query.filter(Coupon.id != existing.id)
            if query.first() is not None:
                errors["code"] = "A coupon with this code already exists for this event."
            else:
                cleaned["code"] = code

    if "discount_percent" in data:
        value = data["discount_percent"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 100:
            errors["discount_percent"] = "Must be an integer from 1 to 100."
        else:
            cleaned["discount_percent"] = value

    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            errors["is_active"] = "Must be a boolean."
        else:
            cleaned["is_active"] = value

    if "allowed_ticket_type_ids" in data:
        value = data["allowed_ticket_type_ids"]
        if not isinstance(value, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in value):
            errors["allowed_ticket_type_ids"] = "Must be a list of integers."
        else:
            ids = set(value)
            valid_ids = {
                row.id
                for row in TicketType.query.filter(
                    TicketType.event_id == event_id, TicketType.id.in_(ids)
                ).all()
            } if ids else set()
            if ids - valid_ids:
                errors["allowed_ticket_type_ids"] = "One or more ticket types are invalid for this event."
            else:
                cleaned["allowed_ticket_type_ids"] = ",".join(str(i) for i in sorted(ids))

    if "max_redemptions" in data:
        value = data["max_redemptions"]
        if value is None:
            cleaned["max_redemptions"] = None
        elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors["max_redemptions"] = "Must be a positive integer, or null for unlimited."
        else:
            cleaned["max_redemptions"] = value

    return cleaned, errors


@admin_coupons_bp.get("/events/<int:event_id>/coupons")
def admin_list_coupons(event_id: int):
    coupons = Coupon.query.filter_by(event_id=event_id).order_by(Coupon.created_at.desc()).all()
    return jsonify({"items": [_serialize_coupon_admin(c) for c in coupons]})


@admin_coupons_bp.post("/events/<int:event_id>/coupons")
def admin_create_coupon(event_id: int):
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_coupon_payload(data, event_id, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    coupon = Coupon(
        event_id=event_id,
        code=cleaned["code"],
        discount_percent=cleaned["discount_percent"],
        is_active=cleaned.get("is_active", True),
        allowed_ticket_type_ids=cleaned.get("allowed_ticket_type_ids", ""),
        max_redemptions=cleaned.get("max_redemptions"),
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(coupon)
    db.session.commit()

    log_action(
        g.current_user,
        "coupon_created",
        f'Created coupon "{coupon.code}" for event {event_id}',
        target_type="coupon",
        target_id=coupon.id,
    )

    return jsonify(_serialize_coupon_admin(coupon)), 201


@admin_coupons_bp.patch("/coupons/<int:coupon_id>")
def admin_update_coupon(coupon_id: int):
    coupon = db.session.get(Coupon, coupon_id)
    if coupon is None:
        return jsonify({"error": "Coupon not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_coupon_payload(data, coupon.event_id, existing=coupon)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(coupon, field, value)
    coupon.updated_by = g.current_user.id

    db.session.commit()

    log_action(
        g.current_user,
        "coupon_updated",
        f'Updated coupon "{coupon.code}"',
        target_type="coupon",
        target_id=coupon.id,
    )

    return jsonify(_serialize_coupon_admin(coupon))
