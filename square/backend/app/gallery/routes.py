from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.gallery.models import Album, Media
from app.lookups.service import all_values
from app.storage.service import get_public_storage

gallery_bp = Blueprint("gallery", __name__, url_prefix="/api/gallery")

MAX_PER_PAGE = 50
MEDIA_DEFAULT_LIMIT = 40
MEDIA_MAX_LIMIT = 100
# Admin-picked, fixed set (see Album.category) — matches the public GalleryView.vue's own
# category filter tags exactly (excluding its "All" meta-option, which isn't a real value).


def _serialize_media(media: Media) -> dict:
    storage = get_public_storage()
    return {
        "id": media.id,
        "filename": media.filename,
        "url": storage.url_for(media.storage_key),
        "thumbnail_url": storage.url_for(media.thumbnail_storage_key),
        "width": media.width,
        "height": media.height,
        "caption": media.caption,
    }


def _serialize_album_summary(album: Album) -> dict:
    cover = album.media[0] if album.media else None
    return {
        "id": album.id,
        "title": album.title,
        "description": album.description,
        "description_style": album.description_style,
        "category": album.category,
        "year": album.year,
        # False only ever appears for an admin previewing an unpublished album.
        "published": album.published,
        "cover_thumbnail_url": (
            get_public_storage().url_for(cover.thumbnail_storage_key) if cover else None
        ),
        # Lets a consumer (the homepage hero) size/pair photos by their real shape instead of
        # guessing — e.g. pairing a naturally taller photo with a taller layout slot.
        "cover_width": cover.width if cover else None,
        "cover_height": cover.height if cover else None,
        "photo_count": len(album.media),
    }


def _serialize_album_detail(album: Album) -> dict:
    return {
        "id": album.id,
        "title": album.title,
        "description": album.description,
        "description_style": album.description_style,
        "event_id": album.event_id,
        "category": album.category,
        "year": album.year,
        "published": album.published,
        "media": [_serialize_media(m) for m in album.media],
    }


@gallery_bp.get("/albums")
def list_albums():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    # An admin's own authenticated request also gets unpublished albums (published: false).
    stmt = select(Album).order_by(Album.created_at.desc())
    if optional_admin_user() is None:
        stmt = stmt.where(Album.published.is_(True))

    event_id = request.args.get("event_id")
    if event_id:
        try:
            stmt = stmt.where(Album.event_id == int(event_id))
        except ValueError:
            return jsonify({"error": "event_id must be an integer"}), 400

    category = request.args.get("category")
    if category:
        if category not in all_values("album_category"):
            return jsonify({"error": f"category must be one of {sorted(all_values('album_category'))}"}), 400
        stmt = stmt.where(Album.category == category)

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_album_summary(album) for album in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


COVERAGE_START_YEAR = 2010
COVERAGE_ERA_YEARS = 5
# Photo-count thresholds (published albums, summed per era): 0 -> none, up to VERY_FEW ->
# very_few, up to PARTIAL -> partial, above -> complete.
COVERAGE_VERY_FEW_MAX = 20
COVERAGE_PARTIAL_MAX = 100


def _coverage_state(photo_count: int) -> str:
    if photo_count == 0:
        return "none"
    if photo_count <= COVERAGE_VERY_FEW_MAX:
        return "very_few"
    if photo_count <= COVERAGE_PARTIAL_MAX:
        return "partial"
    return "complete"


@gallery_bp.get("/coverage")
def archive_coverage():
    """Photo counts per 5-year era from COVERAGE_START_YEAR to the current year, across
    published albums only, for the public "Missing photographs?" band."""
    current_year = datetime.now(timezone.utc).year
    counts_by_year = dict(
        db.session.query(Album.year, func.count(Media.id))
        .join(Media, Media.album_id == Album.id)
        .filter(Album.published.is_(True))
        .group_by(Album.year)
        .all()
    )
    items = []
    for start in range(COVERAGE_START_YEAR, current_year + 1, COVERAGE_ERA_YEARS):
        end = min(start + COVERAGE_ERA_YEARS - 1, current_year)
        count = sum(n for year, n in counts_by_year.items() if start <= year <= end)
        items.append(
            {
                "era": f"{start}–{end}" if end > start else str(start),
                "start_year": start,
                "end_year": end,
                "photo_count": count,
                "state": _coverage_state(count),
            }
        )
    return jsonify({"items": items})


@gallery_bp.get("/albums/<int:album_id>")
def get_album(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None or (not album.published and optional_admin_user() is None):
        return jsonify({"error": "Album not found"}), 404
    return jsonify(_serialize_album_detail(album))


@gallery_bp.get("/media")
def list_media():
    """A flat pool of individual photos across every published album — for a consumer (the
    homepage hero) that wants real photo variety rather than one arbitrary "cover" (album[0])
    per album. Order is recency by default; `?random=1` samples randomly across ALL published albums."""
    try:
        limit = int(request.args.get("limit", MEDIA_DEFAULT_LIMIT))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    if limit < 1:
        return jsonify({"error": "limit must be positive"}), 400
    limit = min(limit, MEDIA_MAX_LIMIT)

    stmt = (
        select(Media)
        .join(Album, Media.album_id == Album.id)
        .where(Album.published.is_(True))
        .order_by(func.random() if request.args.get("random") == "1" else Media.created_at.desc())
        .limit(limit)
    )
    media_items = db.session.execute(stmt).scalars().all()

    return jsonify(
        {
            "items": [
                {**_serialize_media(m), "album_id": m.album_id, "album_title": m.album.title}
                for m in media_items
            ]
        }
    )
