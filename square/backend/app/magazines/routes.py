from flask import Blueprint, jsonify
from sqlalchemy import select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.magazines.models import Magazine

magazines_bp = Blueprint("magazines", __name__, url_prefix="/api/magazines")


def _serialize_magazine(magazine: Magazine) -> dict:
    """Public-safe fields only."""
    return {
        "id": magazine.id,
        "title": magazine.title,
        "slug": magazine.slug,
        "issue_label": magazine.issue_label,
        "issue_date": magazine.issue_date.isoformat() if magazine.issue_date else None,
        "description": magazine.description,
        "description_style": magazine.description_style,
        "pdf_url": magazine.pdf_url,
        "cover_url": magazine.cover_url,
        # False only ever appears for an admin previewing an unpublished magazine.
        "published": magazine.published,
    }


def _visible_stmt():
    stmt = select(Magazine)
    # Admins also get unpublished magazines (published: false) to preview them before going live.
    if optional_admin_user() is None:
        stmt = stmt.where(Magazine.published.is_(True), Magazine.pdf_url.isnot(None))
    return stmt


@magazines_bp.get("")
def list_magazines():
    stmt = _visible_stmt().order_by(Magazine.issue_date.desc().nullslast(), Magazine.id.desc())
    items = db.session.execute(stmt).scalars().all()
    return jsonify({"items": [_serialize_magazine(m) for m in items]})


@magazines_bp.get("/<slug>")
def get_magazine(slug: str):
    magazine = db.session.execute(_visible_stmt().where(Magazine.slug == slug)).scalar_one_or_none()
    if magazine is None:
        return jsonify({"error": "Magazine not found"}), 404
    return jsonify(_serialize_magazine(magazine))
