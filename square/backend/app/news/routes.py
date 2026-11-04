from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.lookups.service import all_values
from app.news.models import News
from app.storage.service import get_public_storage

news_bp = Blueprint("news", __name__, url_prefix="/api/news")

MAX_PER_PAGE = 50


def _read_minutes(article: News) -> int:
    """~200 words/minute, rounded, minimum 1 — computed from `content` rather than stored so an
    edit to the body always keeps the figure honest without a separate write path."""
    word_count = len(article.content.split())
    return max(1, round(word_count / 200))


def _serialize_news_summary(article: News) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "description_style": article.description_style,
        "banner_image": article.banner_image,
        "category": article.category,
        "author": article.author,
        "read_minutes": _read_minutes(article),
        "published_at": article.published_at.isoformat() if article.published_at else None,
        # False only ever appears for an admin previewing a draft/scheduled/archived article.
        "published": _is_published(article),
    }


def _serialize_news_detail(article: News) -> dict:
    storage = get_public_storage()
    return {
        **_serialize_news_summary(article),
        "content": article.content,
        "images": [
            {"id": i.id, "image_url": storage.url_for(i.storage_key), "sort_order": i.sort_order}
            for i in article.images
        ],
    }


def _is_published(article: News) -> bool:
    published_at = article.published_at
    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return (
        article.status == "published"
        and published_at is not None
        and published_at <= datetime.now(timezone.utc)
    )


def _published_filter():
    now = datetime.now(timezone.utc)
    return (News.status == "published") & (News.published_at.isnot(None)) & (News.published_at <= now)


@news_bp.get("")
def list_news():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    category = request.args.get("category")
    if category is not None and category not in all_values("news_category"):
        return jsonify({"error": f"category must be one of {sorted(all_values('news_category'))}"}), 400

    # An admin's own authenticated request also gets drafts/scheduled/archived articles (tagged
    # published: false); drafts have no published_at, so order by it falling back to created_at.
    is_admin = optional_admin_user() is not None
    stmt = select(News).order_by(func.coalesce(News.published_at, News.created_at).desc())
    if not is_admin:
        stmt = stmt.where(_published_filter())
    if category:
        stmt = stmt.where(News.category == category)
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_news_summary(article) for article in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@news_bp.get("/<string:slug>")
def get_news(slug: str):
    stmt = select(News).where(News.slug == slug)
    if optional_admin_user() is None:
        stmt = stmt.where(_published_filter())
    article = db.session.execute(stmt).scalar_one_or_none()
    if article is None:
        return jsonify({"error": "Article not found"}), 404
    return jsonify(_serialize_news_detail(article))
