"""Admin view of newsletter subscribers: list/search, Excel export, and erase (GDPR)."""

import uuid

import bleach

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.auth.decorators import require_role
from app.common.query_params import csv_arg
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.imports.excel import write_xlsx
from app.news.admin_routes import ALLOWED_CONTENT_ATTRIBUTES, ALLOWED_CONTENT_TAGS
from app.newsletter.models import Subscriber
from app.storage.service import get_public_storage

admin_newsletter_bp = Blueprint(
    "admin_newsletter", __name__, url_prefix="/api/admin/newsletter"
)
admin_newsletter_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 100
VALID_STATUSES = {"pending", "subscribed", "unsubscribed"}


def _serialize_subscriber(subscriber: Subscriber) -> dict:
    return {
        "id": subscriber.id,
        "email": subscriber.email,
        "status": subscriber.status,
        "consented_at": subscriber.consented_at.isoformat() if subscriber.consented_at else None,
        "unsubscribed_at": subscriber.unsubscribed_at.isoformat() if subscriber.unsubscribed_at else None,
    }


def _filtered_query():
    query = select(Subscriber)
    q = request.args.get("q", "").strip()
    if q:
        query = query.where(Subscriber.email.ilike(f"%{q}%"))
    statuses = csv_arg("status")
    if statuses:
        query = query.where(Subscriber.status.in_(statuses))
    return query.order_by(Subscriber.created_at.desc(), Subscriber.id.desc())


@admin_newsletter_bp.get("/subscribers")
def list_subscribers():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    if any(s not in VALID_STATUSES for s in csv_arg("status")):
        return jsonify({"error": f"status must be one of {sorted(VALID_STATUSES)}"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    pagination = db.paginate(_filtered_query(), page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_subscriber(s) for s in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
            "subscribed_count": Subscriber.query.filter_by(status="subscribed").count(),
        }
    )


@admin_newsletter_bp.get("/subscribers/export")
def export_subscribers():
    rows = [
        [s.email, s.status, s.consented_at.date().isoformat() if s.consented_at else None]
        for s in db.session.scalars(_filtered_query())
    ]
    data = write_xlsx(["Email", "Status", "Consent given"], rows)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=newsletter-subscribers.xlsx"},
    )


@admin_newsletter_bp.delete("/subscribers/<int:subscriber_id>")
def delete_subscriber(subscriber_id: int):
    subscriber = db.session.get(Subscriber, subscriber_id)
    if subscriber is None:
        return jsonify({"error": "Subscriber not found"}), 404
    db.session.delete(subscriber)
    db.session.commit()
    return "", 204


# ---- Pictures for the Messages editor (newsletters are written and sent in Messages since W14-R20) ----


def sanitize_newsletter_content(html: str) -> str:
    """The News rich-text allow-list plus pictures (`<img src alt>`, http/https only)."""
    return bleach.clean(
        html,
        tags=[*ALLOWED_CONTENT_TAGS, "img"],
        attributes={**ALLOWED_CONTENT_ATTRIBUTES, "img": ["src", "alt"]},
        protocols=["http", "https", "mailto"],
        strip=True,
    )


@admin_newsletter_bp.post("/images")
def upload_image():
    """Upload a picture for use inside a newsletter body. Re-encoded to WebP (<=700KB) like every
    image upload and stored in the public bucket; returns its URL for an <img> in the body. Not
    tied to an issue, so it works before the first save."""
    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400
    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400
    except Exception as exc:  # noqa: BLE001 - log what failed so Render's log shows it
        current_app.logger.warning("Newsletter image upload failed: %s", exc)
        return jsonify({"errors": {"file": "Could not process this image."}}), 400

    storage = get_public_storage()
    safe_name = secure_filename(file.filename or "") or "image"
    storage_key = f"newsletter/{uuid.uuid4().hex}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    return jsonify({"url": storage.url_for(storage_key)}), 201
