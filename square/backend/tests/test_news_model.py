"""Tests for news model (3 tests), e.g. news defaults to draft with no published at; news slug must be unique; news can have a future published at for scheduling."""
from datetime import datetime, timezone

from app import create_app
from app.extensions import db
from app.news.models import News


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_news_defaults_to_draft_with_no_published_at():
    app = _new_app()
    with app.app_context():
        article = News(title="Membership renewal opens", slug="membership-renewal-opens", content="Body text.")
        db.session.add(article)
        db.session.commit()

        saved = News.query.one()
        assert saved.status == "draft"
        assert saved.published_at is None
        db.drop_all()


def test_news_slug_must_be_unique():
    from sqlalchemy.exc import IntegrityError

    app = _new_app()
    with app.app_context():
        db.session.add(News(title="First", slug="dup", content="A"))
        db.session.commit()

        db.session.add(News(title="Second", slug="dup", content="B"))
        try:
            db.session.commit()
            assert False, "expected IntegrityError"
        except IntegrityError:
            db.session.rollback()
        db.drop_all()


def test_news_can_have_a_future_published_at_for_scheduling():
    app = _new_app()
    with app.app_context():
        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        article = News(
            title="Scheduled",
            slug="scheduled",
            content="Body text.",
            status="published",
            published_at=future,
        )
        db.session.add(article)
        db.session.commit()

        saved = News.query.one()
        # SQLite doesn't round-trip tzinfo on DateTime(timezone=True) columns — compare the
        # naive value, matching how other tests in this suite verify via API isoformat instead.
        assert saved.published_at.replace(tzinfo=timezone.utc) == future
        db.drop_all()
