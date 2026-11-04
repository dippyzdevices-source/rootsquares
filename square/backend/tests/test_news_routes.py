"""Tests for news routes (9 tests), e.g. list news only returns published and due articles; list news orders most recently published first; get news returns 404 for a draft article."""
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.news.models import News

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_news(**overrides):
    defaults = {
        "title": "Membership renewal opens",
        "slug": "membership-renewal-opens",
        "content": "Renew your membership online.",
        "status": "draft",
    }
    defaults.update(overrides)
    article = News(**defaults)
    db.session.add(article)
    db.session.commit()
    return article


def test_list_news_only_returns_published_and_due_articles():
    app = _new_app()
    with app.app_context():
        _add_news(title="Draft", slug="draft", status="draft")
        _add_news(title="Archived", slug="archived", status="archived", published_at=NOW - timedelta(days=1))
        _add_news(
            title="Scheduled for the future",
            slug="scheduled",
            status="published",
            published_at=NOW + timedelta(days=1),
        )
        _add_news(title="Live", slug="live", status="published", published_at=NOW - timedelta(days=1))

        response = app.test_client().get("/api/news")
        titles = {item["title"] for item in response.get_json()["items"]}

        assert titles == {"Live"}
        db.drop_all()


def test_list_news_orders_most_recently_published_first():
    app = _new_app()
    with app.app_context():
        _add_news(title="Older", slug="older", status="published", published_at=NOW - timedelta(days=10))
        _add_news(title="Newer", slug="newer", status="published", published_at=NOW - timedelta(days=1))

        response = app.test_client().get("/api/news")
        titles = [item["title"] for item in response.get_json()["items"]]

        assert titles == ["Newer", "Older"]
        db.drop_all()


def test_get_news_returns_404_for_a_draft_article():
    app = _new_app()
    with app.app_context():
        article = _add_news(status="draft")

        response = app.test_client().get(f"/api/news/{article.slug}")

        assert response.status_code == 404
        db.drop_all()


def test_get_news_returns_404_for_a_not_yet_due_scheduled_article():
    app = _new_app()
    with app.app_context():
        article = _add_news(status="published", published_at=NOW + timedelta(days=1))

        response = app.test_client().get(f"/api/news/{article.slug}")

        assert response.status_code == 404
        db.drop_all()


def test_get_news_returns_the_full_article_when_published_and_due():
    app = _new_app()
    with app.app_context():
        article = _add_news(
            status="published",
            published_at=NOW - timedelta(days=1),
            summary="Short summary.",
            content="Full body text.",
        )

        response = app.test_client().get(f"/api/news/{article.slug}")
        data = response.get_json()

        assert response.status_code == 200
        assert data["content"] == "Full body text."
        assert data["summary"] == "Short summary."
        db.drop_all()


def test_get_news_returns_404_for_an_unknown_slug():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/news/does-not-exist")
        assert response.status_code == 404
        db.drop_all()


def test_list_news_filters_by_category():
    app = _new_app()
    with app.app_context():
        _add_news(title="Announcement", slug="announcement", status="published",
                  published_at=NOW - timedelta(days=1), category="announcement")
        _add_news(title="Story", slug="story", status="published",
                  published_at=NOW - timedelta(days=1), category="story")

        response = app.test_client().get("/api/news?category=announcement")
        titles = {item["title"] for item in response.get_json()["items"]}

        assert titles == {"Announcement"}
        db.drop_all()


def test_list_news_rejects_an_invalid_category():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/news?category=not-a-category")
        assert response.status_code == 400
        db.drop_all()


def test_list_news_includes_category_in_the_summary():
    app = _new_app()
    with app.app_context():
        _add_news(status="published", published_at=NOW - timedelta(days=1), category="story")

        response = app.test_client().get("/api/news")
        assert response.get_json()["items"][0]["category"] == "story"
        db.drop_all()
