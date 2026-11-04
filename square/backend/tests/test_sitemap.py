"""Tests for sitemap (5 tests), e.g. sitemap returns xml content type; sitemap includes static pages; sitemap includes published events only."""
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_sitemap_returns_xml_content_type():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/sitemap.xml")
        assert response.status_code == 200
        assert "xml" in response.content_type
        db.drop_all()


def test_sitemap_includes_static_pages():
    app = _new_app()
    app.config["FRONTEND_ORIGIN"] = "http://localhost:5173"
    with app.app_context():
        response = app.test_client().get("/sitemap.xml")
        body = response.get_data(as_text=True)
        assert "<loc>http://localhost:5173/</loc>" in body
        assert "<loc>http://localhost:5173/events</loc>" in body
        assert "<loc>http://localhost:5173/gallery</loc>" in body
        db.drop_all()


def test_sitemap_includes_published_events_only():
    from app.events.models import Event

    app = _new_app()
    with app.app_context():
        db.session.add(Event(title="Durga Puja 2026", slug="durga-puja-2026",
                              event_type="festival", start_datetime=NOW + timedelta(days=10),
                              published=True))
        db.session.add(Event(title="Draft Event", slug="draft-event", event_type="festival",
                              start_datetime=NOW + timedelta(days=20), published=False))
        db.session.commit()

        response = app.test_client().get("/sitemap.xml")
        body = response.get_data(as_text=True)

        assert "/events/durga-puja-2026" in body
        assert "/events/draft-event" not in body
        db.drop_all()


def test_sitemap_includes_published_and_due_news_only():
    from app.news.models import News

    app = _new_app()
    with app.app_context():
        db.session.add(News(title="Published", slug="published-article", content="body",
                             status="published", published_at=NOW - timedelta(days=1)))
        db.session.add(News(title="Draft", slug="draft-article", content="body", status="draft"))
        db.session.add(News(title="Future", slug="future-article", content="body",
                             status="published", published_at=NOW + timedelta(days=1)))
        db.session.commit()

        response = app.test_client().get("/sitemap.xml")
        body = response.get_data(as_text=True)

        assert "/news/published-article" in body
        assert "/news/draft-article" not in body
        assert "/news/future-article" not in body
        db.drop_all()


def test_sitemap_uses_first_frontend_origin_when_several_are_configured():
    app = _new_app()
    app.config["FRONTEND_ORIGIN"] = "https://bca-oslo.org,https://www.bca-oslo.org"
    with app.app_context():
        body = app.test_client().get("/sitemap.xml").get_data(as_text=True)
        assert "<loc>https://bca-oslo.org/events</loc>" in body
        assert "bca-oslo.org,https" not in body
        db.drop_all()
