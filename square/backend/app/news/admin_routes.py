import re
import unicodedata
import uuid
from datetime import datetime, timezone

import bleach
from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.common.description_style import clean_description_style
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.news.models import News, NewsImage
from app.lookups.service import active_values
from app.news.routes import MAX_PER_PAGE
from app.storage.service import get_public_storage

admin_news_bp = Blueprint("admin_news", __name__, url_prefix="/api/admin/news")
admin_news_bp.before_request(require_role("admin"))

VALID_STATUSES = {"draft", "published", "archived"}
# slug is optional on create — generated from the title when omitted (see _generate_unique_slug).
REQUIRED_FIELDS = ("title", "content")

# Matches the rich-text editor's own toolbar scope exactly (bold/italic, headings, lists,
# links) — kept modest on purpose, see the backlog scoping note. Sanitized server-side too,
# never trusting the editor alone: an admin API call bypassing the editor is still a vector.
ALLOWED_CONTENT_TAGS = ["p", "br", "strong", "em", "h2", "h3", "ul", "ol", "li", "a"]
ALLOWED_CONTENT_ATTRIBUTES = {"a": ["href", "rel", "target"]}


def sanitize_news_content(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_CONTENT_TAGS,
        attributes=ALLOWED_CONTENT_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def _user_email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user else None


def _serialize_news_image(image: NewsImage) -> dict:
    return {
        "id": image.id,
        "image_url": get_public_storage().url_for(image.storage_key),
        "sort_order": image.sort_order,
    }


def _serialize_news_admin(article: News) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "description_style": article.description_style,
        "content": article.content,
        "banner_image": article.banner_image,
        "images": [_serialize_news_image(i) for i in article.images],
        "status": article.status,
        "category": article.category,
        "author": article.author,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "created_by_email": _user_email(article.created_by),
        "updated_by_email": _user_email(article.updated_by),
        "created_at": article.created_at.isoformat(),
        "updated_at": article.updated_at.isoformat(),
    }


def _slugify(title: str) -> str:
    text = title.replace("æ", "ae").replace("Æ", "AE").replace("ø", "o").replace("Ø", "O").replace("å", "a").replace("Å", "A")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:200] or "article"


def _generate_unique_slug(title: str) -> str:
    base = _slugify(title)
    slug, n = base, 2
    while db.session.scalar(select(News.id).where(News.slug == slug)) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _validate_news_payload(data: dict, existing: News | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors[field] = "This field is required."

    for field, max_length in (("title", 200), ("slug", 220), ("summary", 500), ("banner_image", 500), ("author", 120)):
        if field not in data:
            continue
        value = data[field]
        if value is None and field in ("summary", "banner_image", "author"):
            cleaned[field] = None
            continue
        if not isinstance(value, str) or not value.strip():
            errors[field] = "Must be a non-empty string."
            continue
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value.strip()

    clean_description_style(data, cleaned, errors)

    if "content" in data:
        value = data["content"]
        if not isinstance(value, str) or not value.strip():
            errors["content"] = "Must be a non-empty string."
        else:
            cleaned["content"] = sanitize_news_content(value)

    if "status" in data:
        value = data["status"]
        if value not in VALID_STATUSES:
            errors["status"] = f"Must be one of {sorted(VALID_STATUSES)}."
        else:
            cleaned["status"] = value

    if "category" in data:
        value = data["category"]
        if value is None:
            cleaned["category"] = None
        # A hidden category is refused for new choices, but an article may keep the one it already has.
        elif value not in active_values("news_category") and not (existing and existing.category == value):
            errors["category"] = f"Must be one of {sorted(active_values('news_category'))}."
        else:
            cleaned["category"] = value

    if "published_at" in data:
        value = data["published_at"]
        if value is None:
            cleaned["published_at"] = None
        else:
            try:
                cleaned["published_at"] = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                errors["published_at"] = "Must be a valid ISO 8601 datetime."

    return cleaned, errors


@admin_news_bp.get("")
def admin_list_news():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt = select(News).order_by(News.created_at.desc())
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(News.title.ilike(like), News.summary.ilike(like)))
    status = (request.args.get("status") or "").strip()
    if status:
        # "scheduled" is published with a future published_at; "published" is already live
        # (the same rule the public listing uses); draft/archived are the stored statuses.
        now = datetime.now(timezone.utc)
        if status == "published":
            stmt = stmt.where(News.status == "published", News.published_at.isnot(None), News.published_at <= now)
        elif status == "scheduled":
            stmt = stmt.where(News.status == "published", News.published_at > now)
        elif status in ("draft", "archived"):
            stmt = stmt.where(News.status == status)
        else:
            return jsonify({"error": "status must be one of ['archived', 'draft', 'published', 'scheduled']"}), 400
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_news_admin(article) for article in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_news_bp.post("")
def admin_create_news():
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_news_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    article = News(
        title=cleaned["title"],
        slug=cleaned.get("slug") or _generate_unique_slug(cleaned["title"]),
        content=cleaned["content"],
        summary=cleaned.get("summary"),
        description_style=cleaned.get("description_style"),
        banner_image=cleaned.get("banner_image"),
        status=cleaned.get("status", "draft"),
        category=cleaned.get("category"),
        author=cleaned.get("author"),
        published_at=cleaned.get("published_at"),
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(article)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": {"slug": "An article with this slug already exists."}}), 409

    return jsonify(_serialize_news_admin(article)), 201


@admin_news_bp.get("/<int:news_id>")
def admin_get_news(news_id: int):
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404
    return jsonify(_serialize_news_admin(article))


@admin_news_bp.post("/<int:news_id>/banner")
def admin_upload_news_banner(news_id: int):
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(article.banner_image) if article.banner_image else None

    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "banner"
    storage_key = f"news/{news_id}/banner-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    article.banner_image = storage.url_for(storage_key)
    article.updated_by = g.current_user.id
    db.session.commit()

    return jsonify(_serialize_news_admin(article))


@admin_news_bp.post("/<int:news_id>/images")
def admin_add_news_image(news_id: int):
    """Appends an additional image to the article's gallery (see NewsImage) — unlike
    admin_upload_news_banner above, which replaces the single lead banner_image, this never
    replaces an existing image."""
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "image"
    storage_key = f"news/{news_id}/image-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)

    next_sort_order = max((i.sort_order for i in article.images), default=-1) + 1
    db.session.add(NewsImage(news_id=news_id, storage_key=storage_key, sort_order=next_sort_order))
    db.session.commit()

    return jsonify(_serialize_news_admin(article)), 201


@admin_news_bp.delete("/<int:news_id>/images/<int:image_id>")
def admin_delete_news_image(news_id: int, image_id: int):
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    image = db.session.get(NewsImage, image_id)
    if image is None or image.news_id != news_id:
        return jsonify({"error": "Image not found"}), 404

    get_public_storage().delete(image.storage_key)
    db.session.delete(image)
    db.session.commit()

    return jsonify(_serialize_news_admin(article))


@admin_news_bp.patch("/<int:news_id>")
def admin_update_news(news_id: int):
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_news_payload(data, existing=article)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(article, field, value)
    article.updated_by = g.current_user.id

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": {"slug": "An article with this slug already exists."}}), 409

    return jsonify(_serialize_news_admin(article))


@admin_news_bp.delete("/<int:news_id>")
def admin_delete_news(news_id: int):
    article = db.session.get(News, news_id)
    if article is None:
        return jsonify({"error": "Article not found"}), 404

    article_title = article.title
    db.session.delete(article)
    db.session.commit()

    log_action(
        g.current_user,
        "news_deleted",
        f'Deleted news article "{article_title}"',
        target_type="news",
        target_id=news_id,
    )

    return "", 204
