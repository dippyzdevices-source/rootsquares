import uuid

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.sponsors.models import Sponsor
from app.sponsors.routes import _serialize_sponsor
from app.storage.service import get_public_storage

admin_sponsors_bp = Blueprint("admin_sponsors", __name__, url_prefix="/api/admin/sponsors")
admin_sponsors_bp.before_request(require_role("admin"))


def _serialize_sponsor_admin(sponsor: Sponsor) -> dict:
    return {
        **_serialize_sponsor(sponsor),
        "display_order": sponsor.display_order,
        "is_active": sponsor.is_active,
        "created_at": sponsor.created_at.isoformat(),
        "updated_at": sponsor.updated_at.isoformat(),
    }


def _validate_payload(data: dict, *, is_create: bool) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if is_create and not data.get("name"):
        errors["name"] = "This field is required."

    if "name" in data and "name" not in errors:
        value = data["name"]
        if not isinstance(value, str) or not value.strip():
            errors["name"] = "Must be a non-empty string."
        elif len(value.strip()) > 200:
            errors["name"] = "Must be at most 200 characters."
        else:
            cleaned["name"] = value.strip()

    if "website_url" in data:
        value = data["website_url"]
        if value is None or (isinstance(value, str) and not value.strip()):
            cleaned["website_url"] = None
        elif not isinstance(value, str) or len(value.strip()) > 500:
            errors["website_url"] = "Must be a URL of at most 500 characters."
        elif not value.strip().lower().startswith(("http://", "https://")):
            errors["website_url"] = "Must start with http:// or https://."
        else:
            cleaned["website_url"] = value.strip()

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


@admin_sponsors_bp.get("")
def admin_list_sponsors():
    sponsors = Sponsor.query.order_by(Sponsor.display_order.asc(), Sponsor.id.asc()).all()
    return jsonify({"items": [_serialize_sponsor_admin(s) for s in sponsors]})


@admin_sponsors_bp.post("")
def admin_create_sponsor():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400

    sponsor = Sponsor(
        name=cleaned["name"],
        website_url=cleaned.get("website_url"),
        display_order=cleaned.get("display_order", 0),
        is_active=cleaned.get("is_active", True),
    )
    db.session.add(sponsor)
    db.session.commit()
    return jsonify(_serialize_sponsor_admin(sponsor)), 201


@admin_sponsors_bp.get("/<int:sponsor_id>")
def admin_get_sponsor(sponsor_id: int):
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        return jsonify({"error": "Sponsor not found"}), 404
    return jsonify(_serialize_sponsor_admin(sponsor))


@admin_sponsors_bp.patch("/<int:sponsor_id>")
def admin_update_sponsor(sponsor_id: int):
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        return jsonify({"error": "Sponsor not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=False)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(sponsor, field, value)
    db.session.commit()
    return jsonify(_serialize_sponsor_admin(sponsor))


@admin_sponsors_bp.delete("/<int:sponsor_id>")
def admin_delete_sponsor(sponsor_id: int):
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        return jsonify({"error": "Sponsor not found"}), 404

    sponsor_name = sponsor.name
    storage = get_public_storage()
    old_key = storage.key_from_url(sponsor.logo_url) if sponsor.logo_url else None
    db.session.delete(sponsor)
    db.session.commit()
    if old_key:
        storage.delete(old_key)

    log_action(
        g.current_user,
        "sponsor_deleted",
        f'Deleted sponsor "{sponsor_name}"',
        target_type="sponsor",
        target_id=sponsor_id,
    )
    return "", 204


@admin_sponsors_bp.post("/<int:sponsor_id>/logo")
def admin_upload_sponsor_logo(sponsor_id: int):
    sponsor = db.session.get(Sponsor, sponsor_id)
    if sponsor is None:
        return jsonify({"error": "Sponsor not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(sponsor.logo_url) if sponsor.logo_url else None

    safe_name = secure_filename(file.filename) or "logo"
    storage_key = f"sponsors/{sponsor.id}/logo-{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    sponsor.logo_url = storage.url_for(storage_key)
    db.session.commit()
    return jsonify(_serialize_sponsor_admin(sponsor))
