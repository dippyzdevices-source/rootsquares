from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from app.auth.decorators import require_role
from app.extensions import db
from app.testimonials.models import Testimonial
from app.testimonials.routes import _serialize_testimonial

admin_testimonials_bp = Blueprint(
    "admin_testimonials", __name__, url_prefix="/api/admin/testimonials"
)
admin_testimonials_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
REQUIRED_FIELDS = ("quote", "author_name")


def _serialize_testimonial_admin(testimonial: Testimonial) -> dict:
    return {
        **_serialize_testimonial(testimonial),
        "sort_order": testimonial.sort_order,
        "is_active": testimonial.is_active,
        "status": testimonial.status,
        "created_at": testimonial.created_at.isoformat(),
        "updated_at": testimonial.updated_at.isoformat(),
    }


def _validate_testimonial_payload(data: dict, existing: Testimonial | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors[field] = "This field is required."

    if "quote" in data:
        value = data["quote"]
        if not isinstance(value, str) or not value.strip():
            errors["quote"] = "Must be a non-empty string."
        else:
            cleaned["quote"] = value.strip()

    if "author_name" in data:
        value = data["author_name"]
        if not isinstance(value, str) or not value.strip():
            errors["author_name"] = "Must be a non-empty string."
        elif len(value) > 200:
            errors["author_name"] = "Must be at most 200 characters."
        else:
            cleaned["author_name"] = value.strip()

    for field, max_length in (("author_context", 200), ("photo_url", 500)):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
            continue
        if not isinstance(value, str) or not value.strip():
            errors[field] = "Must be a non-empty string or null."
            continue
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value.strip()

    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["sort_order"] = "Must be an integer."
        else:
            cleaned["sort_order"] = value

    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            errors["is_active"] = "Must be a boolean."
        else:
            cleaned["is_active"] = value

    if "status" in data:
        value = data["status"]
        if value not in Testimonial.VALID_STATUSES:
            errors["status"] = f"Must be one of {sorted(Testimonial.VALID_STATUSES)}."
        else:
            cleaned["status"] = value

    return cleaned, errors


@admin_testimonials_bp.get("")
def admin_list_testimonials():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    status = request.args.get("status")
    if status and status not in Testimonial.VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(Testimonial.VALID_STATUSES)}"}), 400

    stmt = select(Testimonial).order_by(Testimonial.sort_order.asc())
    if status:
        stmt = stmt.where(Testimonial.status == status)
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Testimonial.author_name.ilike(like), Testimonial.quote.ilike(like)))
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_testimonial_admin(t) for t in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_testimonials_bp.post("")
def admin_create_testimonial():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_testimonial_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    testimonial = Testimonial(
        quote=cleaned["quote"],
        author_name=cleaned["author_name"],
        author_context=cleaned.get("author_context"),
        photo_url=cleaned.get("photo_url"),
        sort_order=cleaned.get("sort_order", 0),
        is_active=cleaned.get("is_active", True),
        # An admin authoring a testimonial directly needs no separate review step — only the
        # public submission endpoint (app/testimonials/routes.py) creates "pending" rows.
        status=cleaned.get("status", "approved"),
    )
    db.session.add(testimonial)
    db.session.commit()

    return jsonify(_serialize_testimonial_admin(testimonial)), 201


@admin_testimonials_bp.get("/<int:testimonial_id>")
def admin_get_testimonial(testimonial_id: int):
    testimonial = db.session.get(Testimonial, testimonial_id)
    if testimonial is None:
        return jsonify({"error": "Testimonial not found"}), 404
    return jsonify(_serialize_testimonial_admin(testimonial))


@admin_testimonials_bp.patch("/<int:testimonial_id>")
def admin_update_testimonial(testimonial_id: int):
    testimonial = db.session.get(Testimonial, testimonial_id)
    if testimonial is None:
        return jsonify({"error": "Testimonial not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_testimonial_payload(data, existing=testimonial)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(testimonial, field, value)

    db.session.commit()
    return jsonify(_serialize_testimonial_admin(testimonial))


@admin_testimonials_bp.delete("/<int:testimonial_id>")
def admin_delete_testimonial(testimonial_id: int):
    testimonial = db.session.get(Testimonial, testimonial_id)
    if testimonial is None:
        return jsonify({"error": "Testimonial not found"}), 404

    db.session.delete(testimonial)
    db.session.commit()

    return "", 204
