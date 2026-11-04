import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.committee.models import CommitteeMember
from app.committee.routes import _serialize_committee_member
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.storage.service import get_public_storage

admin_committee_bp = Blueprint("admin_committee", __name__, url_prefix="/api/admin/committee")
admin_committee_bp.before_request(require_role("admin"))

REQUIRED_FIELDS = ("name", "role")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_MEMBER_SINCE_YEAR = 1900


def _serialize_committee_member_admin(member: CommitteeMember) -> dict:
    return {
        **_serialize_committee_member(member),
        "display_order": member.display_order,
        "is_active": member.is_active,
        "created_at": member.created_at.isoformat(),
        "updated_at": member.updated_at.isoformat(),
    }


def _validate_payload(data: dict, *, is_create: bool) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if is_create:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors[field] = "This field is required."

    for field, max_length in (
        ("name", 200),
        ("role", 200),
        ("sub_name", 200),
        ("address", 300),
        ("email", 255),
        ("phone", 50),
    ):
        if field not in data:
            continue
        value = data[field]
        if value is None and field in ("sub_name", "address", "email", "phone"):
            cleaned[field] = None
            continue
        if not isinstance(value, str) or not value.strip():
            errors[field] = "Must be a non-empty string."
            continue
        value = value.strip()
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        if field == "email" and not EMAIL_RE.match(value):
            errors[field] = "Enter a valid email address."
            continue
        cleaned[field] = value

    if "member_since" in data:
        value = data["member_since"]
        current_year = datetime.now(timezone.utc).year
        if value is None:
            cleaned["member_since"] = None
        elif isinstance(value, bool) or not isinstance(value, int):
            errors["member_since"] = "Must be a whole year."
        elif value < MIN_MEMBER_SINCE_YEAR or value > current_year:
            errors["member_since"] = f"Must be between {MIN_MEMBER_SINCE_YEAR} and {current_year}."
        else:
            cleaned["member_since"] = value

    if "quote" in data:
        value = data["quote"]
        if value is None:
            cleaned["quote"] = None
        elif not isinstance(value, str):
            errors["quote"] = "Must be a string or null."
        else:
            cleaned["quote"] = value.strip() or None

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


@admin_committee_bp.get("")
def admin_list_committee_members():
    members = CommitteeMember.query.order_by(CommitteeMember.display_order.asc()).all()
    return jsonify({"items": [_serialize_committee_member_admin(m) for m in members]})


@admin_committee_bp.post("")
def admin_create_committee_member():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400

    member = CommitteeMember(
        name=cleaned["name"],
        sub_name=cleaned.get("sub_name"),
        role=cleaned["role"],
        address=cleaned.get("address"),
        email=cleaned.get("email"),
        phone=cleaned.get("phone"),
        member_since=cleaned.get("member_since"),
        quote=cleaned.get("quote"),
        display_order=cleaned.get("display_order", 0),
        is_active=cleaned.get("is_active", True),
    )
    db.session.add(member)
    db.session.commit()

    return jsonify(_serialize_committee_member_admin(member)), 201


@admin_committee_bp.get("/<int:member_id>")
def admin_get_committee_member(member_id: int):
    member = db.session.get(CommitteeMember, member_id)
    if member is None:
        return jsonify({"error": "Committee member not found"}), 404
    return jsonify(_serialize_committee_member_admin(member))


@admin_committee_bp.patch("/<int:member_id>")
def admin_update_committee_member(member_id: int):
    member = db.session.get(CommitteeMember, member_id)
    if member is None:
        return jsonify({"error": "Committee member not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=False)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(member, field, value)

    db.session.commit()
    return jsonify(_serialize_committee_member_admin(member))


@admin_committee_bp.delete("/<int:member_id>")
def admin_delete_committee_member(member_id: int):
    member = db.session.get(CommitteeMember, member_id)
    if member is None:
        return jsonify({"error": "Committee member not found"}), 404

    member_name = member.name
    db.session.delete(member)
    db.session.commit()

    log_action(
        g.current_user,
        "committee_member_deleted",
        f'Deleted committee member "{member_name}"',
        target_type="committee_member",
        target_id=member_id,
    )

    return "", 204


@admin_committee_bp.post("/<int:member_id>/photo")
def admin_upload_committee_photo(member_id: int):
    """Mirrors app/members/routes.py's upload_my_photo — same single-image, no-thumbnail
    upload flow, just keyed under committee/ instead of members/."""
    member = db.session.get(CommitteeMember, member_id)
    if member is None:
        return jsonify({"error": "Committee member not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(member.portrait_url) if member.portrait_url else None

    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "portrait"
    storage_key = f"committee/{member.id}/portrait-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    member.portrait_url = storage.url_for(storage_key)
    db.session.commit()

    return jsonify(_serialize_committee_member_admin(member))
