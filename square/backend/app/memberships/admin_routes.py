"""Admin management of Membership records (create/update only — no delete).

Membership rows are historical (one per renewal/type-change, see models.py), so an admin
corrects a mistake or ends a membership via `status`/`end_date`, never by deleting a row.

Protected by role-based auth — every route in this blueprint requires the "admin" role via
the before_request hook below. See app/auth/decorators.py for require_role.
"""

from datetime import date

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.members.models import Member
from app.memberships.emails import send_membership_active_email
from app.memberships.models import Membership, MembershipType
from app.memberships.routes import (
    VALID_BILLING_FREQUENCIES,
    VALID_MEMBERSHIP_STATUSES,
    _serialize_membership,
    _serialize_membership_type_raw,
)
from app.memberships.service import (
    activate_membership,
    awaiting_payment_clause,
    membership_rule_error,
    resync_periods_after_type_change,
)

admin_memberships_bp = Blueprint(
    "admin_memberships", __name__, url_prefix="/api/admin/memberships"
)
admin_memberships_bp.before_request(require_role("admin"))

admin_membership_types_bp = Blueprint(
    "admin_membership_types", __name__, url_prefix="/api/admin/membership-types"
)
admin_membership_types_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 100


def _all_membership_type_names() -> set[str]:
    # Admin operations (unlike the self-service renewal request) may reference a deactivated
    # type too — e.g. correcting historical data or importing a legacy Excel roster.
    return {name for (name,) in db.session.query(MembershipType.name).all()}


def _serialize_membership_admin(membership: Membership) -> dict:
    member = membership.member
    return {
        **_serialize_membership(membership),
        "member_id": membership.member_id,
        "member_name": member.name,
        # A member imported via Excel has no linked User yet — fall back to their own
        # email, matching every other admin serializer's member.user.email/.email pattern.
        "member_email": member.user.email if member.user else member.email,
    }


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _validate_membership_payload(data: dict, existing: Membership | None) -> tuple[dict, dict]:
    """Validate and clean a create/update payload.

    Required fields (membership_type, start_date) are only enforced when `existing` is None
    (create). Returns (cleaned_fields, errors) — apply cleaned_fields only if errors is empty.
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        if not data.get("membership_type"):
            errors["membership_type"] = "This field is required."
        if not data.get("start_date"):
            errors["start_date"] = "This field is required."

    if "membership_type" in data:
        membership_type = data["membership_type"]
        valid_types = _all_membership_type_names()
        if membership_type not in valid_types:
            errors["membership_type"] = f"Must be one of {sorted(valid_types)}."
        else:
            cleaned["membership_type"] = membership_type

    if "status" in data:
        status = data["status"]
        if status not in VALID_MEMBERSHIP_STATUSES:
            errors["status"] = f"Must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}."
        else:
            cleaned["status"] = status

    for field in ("start_date", "end_date"):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
            continue
        try:
            cleaned[field] = _parse_date(value)
        except (ValueError, TypeError):
            errors[field] = "Must be a valid ISO 8601 date (YYYY-MM-DD)."

    start = cleaned.get("start_date", existing.start_date if existing else None)
    end = cleaned.get("end_date", existing.end_date if existing else None)
    if start and end and end < start:
        errors["end_date"] = "Must not be before start_date."

    return cleaned, errors


@admin_memberships_bp.get("")
def admin_list_memberships():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt = select(Membership).order_by(Membership.id.desc())

    status = request.args.get("status")
    if status:
        if status not in VALID_MEMBERSHIP_STATUSES:
            return jsonify({"error": f"status must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}"}), 400
        stmt = stmt.where(Membership.status == status)
        if status == "pending":
            # Requests still waiting for their first payment activate themselves — not for review.
            stmt = stmt.where(~awaiting_payment_clause())

    membership_type = request.args.get("membership_type")
    if membership_type:
        valid_types = _all_membership_type_names()
        if membership_type not in valid_types:
            return jsonify({"error": f"membership_type must be one of {sorted(valid_types)}"}), 400
        stmt = stmt.where(Membership.membership_type == membership_type)

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_membership_admin(m) for m in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_memberships_bp.post("")
def admin_create_membership():
    data = request.get_json(silent=True) or {}

    member_id = data.get("member_id")
    member = db.session.get(Member, member_id) if member_id else None
    if member is None:
        return jsonify({"errors": {"member_id": "Must reference an existing member."}}), 400

    cleaned, errors = _validate_membership_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    rule_error = membership_rule_error(member, cleaned["membership_type"])
    if rule_error:
        return jsonify({"errors": {"membership_type": rule_error}}), 400

    membership = Membership(
        member_id=member.id,
        membership_type=cleaned["membership_type"],
        status=cleaned.get("status", "pending"),
        start_date=cleaned["start_date"],
        end_date=cleaned.get("end_date"),
    )
    db.session.add(membership)
    db.session.commit()

    if membership.status == "active":
        activate_membership(membership)
        send_membership_active_email(membership)

    return jsonify(_serialize_membership(membership)), 201


@admin_memberships_bp.patch("/<int:membership_id>")
def admin_update_membership(membership_id: int):
    membership = db.session.get(Membership, membership_id)
    if membership is None:
        return jsonify({"error": "Membership not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_membership_payload(data, existing=membership)
    if errors:
        return jsonify({"errors": errors}), 400

    final_type = cleaned.get("membership_type", membership.membership_type)
    if "membership_type" in cleaned or cleaned.get("status") == "active":
        rule_error = membership_rule_error(membership.member, final_type)
        if rule_error:
            return jsonify({"errors": {"membership_type": rule_error}}), 400

    old_type = membership.membership_type
    was_active = membership.status == "active"
    for field, value in cleaned.items():
        setattr(membership, field, value)

    db.session.commit()

    if "membership_type" in cleaned:
        # Also runs when the value is unchanged — that re-save is how a membership already left
        # in a mixed state gets cleaned up.
        resync_periods_after_type_change(membership, old_type)
    if "status" in cleaned and membership.status == "active":
        activate_membership(membership)
        if not was_active:  # only the moment it becomes active, not a re-save of an active one
            send_membership_active_email(membership)

    if "status" in cleaned:
        log_action(
            g.current_user,
            "membership_status_changed",
            f"Changed {membership.member.name}'s membership status to {membership.status}",
            target_type="membership",
            target_id=membership.id,
        )

    return jsonify(_serialize_membership(membership))


def _serialize_membership_type_admin(membership_type: MembershipType) -> dict:
    return {
        **_serialize_membership_type_raw(membership_type),
        "is_active": membership_type.is_active,
        "sort_order": membership_type.sort_order,
    }


def _validate_membership_type_payload(data: dict, existing: MembershipType | None) -> tuple[dict, dict]:
    """Same (cleaned, errors) shape as _validate_membership_payload. `name` is only accepted
    on create — it's the primary key and every existing Membership row references it by value,
    so renaming isn't supported (see MembershipType's docstring).
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "This field is required."
        elif len(name.strip()) > 20:
            errors["name"] = "Must be at most 20 characters."
        elif db.session.get(MembershipType, name.strip().lower()) is not None:
            errors["name"] = "A membership type with this name already exists."
        else:
            cleaned["name"] = name.strip().lower()
        if data.get("price") is None:
            errors["price"] = "This field is required."

    if "price" in data:
        value = data["price"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["price"] = "Must be a non-negative whole number of kroner."
        else:
            cleaned["price"] = value

    if "billing_frequency" in data:
        value = data["billing_frequency"]
        if value not in VALID_BILLING_FREQUENCIES:
            errors["billing_frequency"] = f"Must be one of {sorted(VALID_BILLING_FREQUENCIES)}."
        else:
            cleaned["billing_frequency"] = value

    if "description" in data:
        value = data["description"]
        if value is None or (isinstance(value, str) and not value.strip()):
            cleaned["description"] = None
        elif not isinstance(value, str) or len(value.strip()) > 300:
            errors["description"] = "Must be text of at most 300 characters."
        else:
            cleaned["description"] = value.strip()

    if "contact_for_price" in data:
        value = data["contact_for_price"]
        if not isinstance(value, bool):
            errors["contact_for_price"] = "Must be a boolean."
        else:
            cleaned["contact_for_price"] = value

    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            errors["is_active"] = "Must be a boolean."
        else:
            cleaned["is_active"] = value

    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["sort_order"] = "Must be an integer."
        else:
            cleaned["sort_order"] = value

    return cleaned, errors


@admin_membership_types_bp.get("")
def admin_list_membership_types():
    types = MembershipType.query.order_by(MembershipType.sort_order, MembershipType.name).all()
    return jsonify({"items": [_serialize_membership_type_admin(t) for t in types]})


@admin_membership_types_bp.post("")
def admin_create_membership_type():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_membership_type_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    membership_type = MembershipType(
        name=cleaned["name"],
        price=cleaned["price"],
        billing_frequency=cleaned.get("billing_frequency", "yearly"),
        contact_for_price=cleaned.get("contact_for_price", False),
        description=cleaned.get("description"),
        is_active=cleaned.get("is_active", True),
        sort_order=cleaned.get("sort_order", 0),
    )
    db.session.add(membership_type)
    db.session.commit()

    return jsonify(_serialize_membership_type_admin(membership_type)), 201


@admin_membership_types_bp.patch("/<name>")
def admin_update_membership_type(name: str):
    membership_type = db.session.get(MembershipType, name)
    if membership_type is None:
        return jsonify({"error": "Membership type not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_membership_type_payload(data, existing=membership_type)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(membership_type, field, value)

    db.session.commit()
    return jsonify(_serialize_membership_type_admin(membership_type))
