import logging
import re
import uuid
from datetime import date

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.common.description_style import clean_description_style
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.magazines.models import Magazine
from app.magazines.routes import _serialize_magazine
from app.storage.service import get_public_storage

logger = logging.getLogger(__name__)

admin_magazines_bp = Blueprint("admin_magazines", __name__, url_prefix="/api/admin/magazines")
admin_magazines_bp.before_request(require_role("admin"))

MAX_PDF_BYTES = 25 * 1024 * 1024


def _serialize_magazine_admin(magazine: Magazine) -> dict:
    return {
        **_serialize_magazine(magazine),
        "created_at": magazine.created_at.isoformat(),
        "updated_at": magazine.updated_at.isoformat(),
    }


def _generate_unique_slug(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "magazine"
    slug, n = base, 2
    while Magazine.query.filter_by(slug=slug).first() is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _validate_payload(data: dict, *, is_create: bool, existing: Magazine | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if is_create and not data.get("title"):
        errors["title"] = "This field is required."

    for field, max_length in (("title", 200), ("issue_label", 100), ("description", 1000)):
        if field not in data or field in errors:
            continue
        value = data[field]
        if value is None and field != "title":
            cleaned[field] = None
            continue
        if not isinstance(value, str) or (field == "title" and not value.strip()):
            errors[field] = "Must be a non-empty string." if field == "title" else "Must be a string."
            continue
        value = value.strip()
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value or None

    clean_description_style(data, cleaned, errors)

    if "issue_date" in data:
        value = data["issue_date"]
        if value in (None, ""):
            cleaned["issue_date"] = None
        else:
            try:
                cleaned["issue_date"] = date.fromisoformat(value)
            except (TypeError, ValueError):
                errors["issue_date"] = "Must be a date in YYYY-MM-DD format."

    if "published" in data:
        value = data["published"]
        if not isinstance(value, bool):
            errors["published"] = "Must be a boolean."
        elif value and (existing is None or not existing.pdf_url):
            errors["published"] = "Upload the PDF before publishing."
        else:
            cleaned["published"] = value

    return cleaned, errors


@admin_magazines_bp.get("")
def admin_list_magazines():
    items = Magazine.query.order_by(Magazine.issue_date.desc().nullslast(), Magazine.id.desc()).all()
    return jsonify({"items": [_serialize_magazine_admin(m) for m in items]})


@admin_magazines_bp.post("")
def admin_create_magazine():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=True, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    magazine = Magazine(
        title=cleaned["title"],
        slug=_generate_unique_slug(cleaned["title"]),
        issue_label=cleaned.get("issue_label"),
        issue_date=cleaned.get("issue_date"),
        description=cleaned.get("description"),
        description_style=cleaned.get("description_style"),
        published=False,
        created_by=g.current_user.id,
    )
    db.session.add(magazine)
    db.session.commit()
    return jsonify(_serialize_magazine_admin(magazine)), 201


@admin_magazines_bp.get("/<int:magazine_id>")
def admin_get_magazine(magazine_id: int):
    magazine = db.session.get(Magazine, magazine_id)
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404
    return jsonify(_serialize_magazine_admin(magazine))


@admin_magazines_bp.patch("/<int:magazine_id>")
def admin_update_magazine(magazine_id: int):
    magazine = db.session.get(Magazine, magazine_id)
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_payload(data, is_create=False, existing=magazine)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(magazine, field, value)
    db.session.commit()
    return jsonify(_serialize_magazine_admin(magazine))


@admin_magazines_bp.delete("/<int:magazine_id>")
def admin_delete_magazine(magazine_id: int):
    magazine = db.session.get(Magazine, magazine_id)
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404

    title = magazine.title
    storage = get_public_storage()
    keys = [
        storage.key_from_url(url)
        for url in (magazine.pdf_url, magazine.cover_url)
        if url
    ]
    db.session.delete(magazine)
    db.session.commit()
    for key in keys:
        if key:
            storage.delete(key)

    log_action(
        g.current_user,
        "magazine_deleted",
        f'Deleted magazine "{title}"',
        target_type="magazine",
        target_id=magazine_id,
    )
    return "", 204


@admin_magazines_bp.post("/<int:magazine_id>/pdf")
def admin_upload_magazine_pdf(magazine_id: int):
    magazine = db.session.get(Magazine, magazine_id)
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    data = file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        return jsonify({"errors": {"file": "The PDF is too large (limit 25MB)."}}), 400
    if not data.startswith(b"%PDF-"):
        logger.warning("Magazine %s: rejected non-PDF upload %r", magazine_id, file.filename)
        return jsonify({"errors": {"file": "This file is not a PDF."}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(magazine.pdf_url) if magazine.pdf_url else None

    safe_name = secure_filename(file.filename) or "magazine.pdf"
    storage_key = f"magazines/{magazine.id}/issue-{uuid.uuid4().hex}-{safe_name}"
    try:
        storage.upload(storage_key, data, "application/pdf")
    except Exception:
        logger.exception("Magazine %s: PDF storage upload failed", magazine_id)
        return jsonify({"errors": {"file": "Could not save this PDF to storage."}}), 500
    if old_key:
        storage.delete(old_key)

    magazine.pdf_url = storage.url_for(storage_key)
    db.session.commit()
    return jsonify(_serialize_magazine_admin(magazine))


@admin_magazines_bp.post("/<int:magazine_id>/cover")
def admin_upload_magazine_cover(magazine_id: int):
    magazine = db.session.get(Magazine, magazine_id)
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(magazine.cover_url) if magazine.cover_url else None

    safe_name = secure_filename(file.filename) or "cover"
    storage_key = f"magazines/{magazine.id}/cover-{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    magazine.cover_url = storage.url_for(storage_key)
    db.session.commit()
    return jsonify(_serialize_magazine_admin(magazine))
