from datetime import datetime, timezone

import uuid

import logging

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.common.description_style import clean_description_style
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.gallery.models import Album, Media
from app.gallery.routes import MAX_PER_PAGE, _serialize_media
from app.lookups.service import active_values
from app.storage.service import get_public_storage

logger = logging.getLogger(__name__)

admin_gallery_bp = Blueprint("admin_gallery", __name__, url_prefix="/api/admin/gallery")
admin_gallery_bp.before_request(require_role("admin"))


def _user_email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user else None


def _serialize_album_admin(album: Album) -> dict:
    return {
        "id": album.id,
        "title": album.title,
        "description": album.description,
        "description_style": album.description_style,
        "event_id": album.event_id,
        "category": album.category,
        "year": album.year,
        "published": album.published,
        "created_by_email": _user_email(album.created_by),
        "updated_by_email": _user_email(album.updated_by),
        "created_at": album.created_at.isoformat(),
        "updated_at": album.updated_at.isoformat(),
        "media": [_serialize_media(m) for m in album.media],
    }


def _validate_album_payload(data: dict, existing: Album | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None and not data.get("title"):
        errors["title"] = "This field is required."

    if "title" in data:
        value = data["title"]
        if not isinstance(value, str) or not value.strip():
            errors["title"] = "Must be a non-empty string."
        elif len(value) > 200:
            errors["title"] = "Must be at most 200 characters."
        else:
            cleaned["title"] = value.strip()

    if "description" in data:
        value = data["description"]
        if value is not None and not isinstance(value, str):
            errors["description"] = "Must be a string."
        else:
            cleaned["description"] = value

    clean_description_style(data, cleaned, errors)

    if "event_id" in data:
        value = data["event_id"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            errors["event_id"] = "Must be an integer or null."
        else:
            cleaned["event_id"] = value

    if existing is None and "year" not in data:
        errors["year"] = "This field is required."

    if "year" in data:
        value = data["year"]
        max_year = datetime.now(timezone.utc).year
        if isinstance(value, bool) or not isinstance(value, int) or not 1900 <= value <= max_year:
            errors["year"] = f"Must be a year between 1900 and {max_year}."
        else:
            cleaned["year"] = value

    if "category" in data:
        value = data["category"]
        # A hidden category is refused for new choices, but an album may keep the one it already has.
        if value is not None and value not in active_values("album_category") and not (existing and existing.category == value):
            errors["category"] = f"Must be one of {sorted(active_values('album_category'))} or null."
        else:
            cleaned["category"] = value

    if "published" in data:
        value = data["published"]
        if not isinstance(value, bool):
            errors["published"] = "Must be a boolean."
        else:
            cleaned["published"] = value

    return cleaned, errors


@admin_gallery_bp.get("/albums")
def admin_list_albums():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt = select(Album).order_by(Album.created_at.desc())
    q = (request.args.get("q") or "").strip()
    if q:
        stmt = stmt.where(Album.title.ilike(f"%{q}%"))
    published = (request.args.get("published") or "").strip().lower()
    if published in ("true", "false"):
        stmt = stmt.where(Album.published.is_(published == "true"))
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_album_admin(album) for album in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_gallery_bp.post("/albums")
def admin_create_album():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_album_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    album = Album(
        title=cleaned["title"],
        description=cleaned.get("description"),
        description_style=cleaned.get("description_style"),
        event_id=cleaned.get("event_id"),
        category=cleaned.get("category"),
        year=cleaned["year"],
        published=cleaned.get("published", False),
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(album)
    db.session.commit()

    return jsonify(_serialize_album_admin(album)), 201


@admin_gallery_bp.get("/albums/<int:album_id>")
def admin_get_album(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None:
        return jsonify({"error": "Album not found"}), 404
    return jsonify(_serialize_album_admin(album))


@admin_gallery_bp.patch("/albums/<int:album_id>")
def admin_update_album(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None:
        return jsonify({"error": "Album not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_album_payload(data, existing=album)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(album, field, value)
    album.updated_by = g.current_user.id

    db.session.commit()
    return jsonify(_serialize_album_admin(album))


@admin_gallery_bp.delete("/albums/<int:album_id>")
def admin_delete_album(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None:
        return jsonify({"error": "Album not found"}), 404

    album_title = album.title
    storage = get_public_storage()
    for media in album.media:
        storage.delete(media.storage_key)
        storage.delete(media.thumbnail_storage_key)

    db.session.delete(album)
    db.session.commit()

    log_action(
        g.current_user,
        "gallery_album_deleted",
        f'Deleted album "{album_title}"',
        target_type="album",
        target_id=album_id,
    )

    return "", 204


@admin_gallery_bp.post("/albums/<int:album_id>/media")
def admin_upload_media(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None:
        return jsonify({"error": "Album not found"}), 404

    files = request.files.getlist("files")
    if not files:
        return jsonify({"errors": {"files": "At least one file is required."}}), 400

    storage = get_public_storage()
    created = []
    errors = []

    for file in files:
        try:
            processed = process_upload(file)
        except MediaValidationError as exc:
            logger.warning("Gallery upload rejected (album %s, %r): %s", album_id, file.filename, exc)
            errors.append({"filename": file.filename, "error": str(exc)})
            continue
        except Exception:
            logger.exception("Gallery upload failed while processing (album %s, %r)", album_id, file.filename)
            errors.append({"filename": file.filename, "error": "Could not process this image."})
            continue

        unique_id = uuid.uuid4().hex
        safe_name = secure_filename(file.filename) or "upload"
        storage_key = f"gallery/{album_id}/{unique_id}-{safe_name}"
        thumbnail_key = f"gallery/{album_id}/thumbnails/{unique_id}-{safe_name}.jpg"

        try:
            storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
            storage.upload(thumbnail_key, processed.thumbnail_bytes, "image/jpeg")
        except Exception:
            logger.exception("Gallery upload failed while storing (album %s, %r)", album_id, file.filename)
            errors.append({"filename": file.filename, "error": "Could not save this image to storage."})
            continue

        media = Media(
            album_id=album_id,
            filename=file.filename or safe_name,
            storage_key=storage_key,
            thumbnail_storage_key=thumbnail_key,
            mime_type=processed.original_content_type,
            width=processed.width,
            height=processed.height,
            uploaded_by=g.current_user.id,
        )
        db.session.add(media)
        db.session.flush()
        created.append(_serialize_media(media))

    if not created:
        db.session.rollback()
        return jsonify({"created": [], "errors": errors}), 400

    db.session.commit()
    return jsonify({"created": created, "errors": errors}), 201


@admin_gallery_bp.patch("/media/<int:media_id>")
def admin_update_media(media_id: int):
    media = db.session.get(Media, media_id)
    if media is None:
        return jsonify({"error": "Media not found"}), 404

    data = request.get_json(silent=True) or {}
    if "caption" not in data:
        return jsonify({"errors": {"caption": "This field is required."}}), 400

    value = data["caption"]
    if value is not None and not isinstance(value, str):
        return jsonify({"errors": {"caption": "Must be a string or null."}}), 400
    if isinstance(value, str) and len(value) > 300:
        return jsonify({"errors": {"caption": "Must be at most 300 characters."}}), 400

    media.caption = value.strip() if isinstance(value, str) and value.strip() else None
    db.session.commit()

    return jsonify(_serialize_media(media))


@admin_gallery_bp.delete("/media/<int:media_id>")
def admin_delete_media(media_id: int):
    media = db.session.get(Media, media_id)
    if media is None:
        return jsonify({"error": "Media not found"}), 404

    album_title = media.album.title
    storage = get_public_storage()
    storage.delete(media.storage_key)
    storage.delete(media.thumbnail_storage_key)

    db.session.delete(media)
    db.session.commit()

    log_action(
        g.current_user,
        "gallery_media_deleted",
        f'Deleted a photo from album "{album_title}"',
        target_type="media",
        target_id=media_id,
    )

    return "", 204
