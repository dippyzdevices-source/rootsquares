import uuid

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.founders.models import Founder
from app.founders.routes import _serialize_founder
from app.gallery.media_processing import MediaValidationError, process_upload
from app.storage.service import get_public_storage

admin_founders_bp = Blueprint("admin_founders", __name__, url_prefix="/api/admin/founders")
admin_founders_bp.before_request(require_role("admin"))

REQUIRED_FIELDS = ("name", "role", "quote")


def _serialize_founder_admin(founder: Founder) -> dict:
    return {
        **_serialize_founder(founder),
        "display_order": founder.display_order,
        "is_active": founder.is_active,
        "created_at": founder.created_at.isoformat(),
        "updated_at": founder.updated_at.isoformat(),
    }


def _validate_payload(data: dict, *, is_create: bool) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if is_create:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors[field] = "This field is required."

    for field, max_length in (("name", 200), ("role", 200), ("sub_name", 200), ("quote", 3000)):
        if field not in data:
            continue
        value = data[field]
        if value is None and field == "sub_name":
            cleaned[field] = None
            continue
        if not isinstance(value, str) or not value.strip():
            errors[field] = "Must be a non-empty string."
            continue
        value = value.strip()
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value

    if "display_order" in data:
        value = data["display_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["display_order"] = "Must be an integer."
        else:
            cleaned["display_order"] = value

    if "is_active" in data:
        value = data["is_active"]
        if not isinstance(value, bool):
            errors["is_active"] = "Must be a boolean."
        else:
            cleaned["is_active"] = value

    return cleaned, errors


@admin_founders_bp.get("")
def admin_list_founders():
    founders = Founder.query.order_by(Founder.display_order.asc(), Founder.id.asc()).all()
    return jsonify({"items": [_serialize_founder_admin(f) for f in founders]})


@admin_founders_bp.post("")
def admin_create_founder():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400

    founder = Founder(
        name=cleaned["name"],
        sub_name=cleaned.get("sub_name"),
        role=cleaned["role"],
        quote=cleaned["quote"],
        display_order=cleaned.get("display_order", 0),
        is_active=cleaned.get("is_active", True),
    )
    db.session.add(founder)
    db.session.commit()
    return jsonify(_serialize_founder_admin(founder)), 201


@admin_founders_bp.get("/<int:founder_id>")
def admin_get_founder(founder_id: int):
    founder = db.session.get(Founder, founder_id)
    if founder is None:
        return jsonify({"error": "Founder not found"}), 404
    return jsonify(_serialize_founder_admin(founder))


@admin_founders_bp.patch("/<int:founder_id>")
def admin_update_founder(founder_id: int):
    founder = db.session.get(Founder, founder_id)
    if founder is None:
        return jsonify({"error": "Founder not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=False)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(founder, field, value)
    db.session.commit()
    return jsonify(_serialize_founder_admin(founder))


@admin_founders_bp.delete("/<int:founder_id>")
def admin_delete_founder(founder_id: int):
    founder = db.session.get(Founder, founder_id)
    if founder is None:
        return jsonify({"error": "Founder not found"}), 404

    founder_name = founder.name
    db.session.delete(founder)
    db.session.commit()

    log_action(
        g.current_user,
        "founder_deleted",
        f'Deleted founder "{founder_name}"',
        target_type="founder",
        target_id=founder_id,
    )
    return "", 204


@admin_founders_bp.post("/<int:founder_id>/photo")
def admin_upload_founder_photo(founder_id: int):
    """Same single-image upload flow as the committee portrait, keyed under founders/."""
    founder = db.session.get(Founder, founder_id)
    if founder is None:
        return jsonify({"error": "Founder not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(founder.portrait_url) if founder.portrait_url else None

    safe_name = secure_filename(file.filename) or "portrait"
    storage_key = f"founders/{founder.id}/portrait-{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    founder.portrait_url = storage.url_for(storage_key)
    db.session.commit()
    return jsonify(_serialize_founder_admin(founder))
