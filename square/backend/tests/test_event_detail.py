"""Tests for event detail (6 tests), e.g. get event returns full detail for published event; get event includes ordered banners; get event returns 404 for unpublished event."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.events.models import Event
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_event(**overrides):
    defaults = {"event_type": "festival", "published": True}
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def test_get_event_returns_full_detail_for_published_event():
    app = _new_app()
    with app.app_context():
        _add_event(
            title="Durga Puja 2026",
            slug="durga-puja-2026",
            description="Four days of celebration.",
            venue="Oslo Kulturhus",
            address="Youngs gate 6, Oslo",
            capacity=500,
            start_datetime=NOW + timedelta(days=10),
        )

        response = app.test_client().get("/api/events/durga-puja-2026")
        data = response.get_json()

        assert response.status_code == 200
        assert data["title"] == "Durga Puja 2026"
        assert data["description"] == "Four days of celebration."
        assert data["address"] == "Youngs gate 6, Oslo"
        assert data["capacity"] == 500
        assert data["banners"] == []

        db.drop_all()


def test_get_event_includes_ordered_banners():
    from app.events.models import EventBanner

    app = _new_app()
    with app.app_context():
        event = _add_event(
            title="Durga Puja 2026",
            slug="durga-puja-2026",
            start_datetime=NOW + timedelta(days=10),
        )
        db.session.add(EventBanner(event_id=event.id, storage_key="events/1/second.jpg", sort_order=1))
        db.session.add(EventBanner(event_id=event.id, storage_key="events/1/first.jpg", sort_order=0))
        db.session.commit()

        response = app.test_client().get("/api/events/durga-puja-2026")
        data = response.get_json()

        assert response.status_code == 200
        assert [b["sort_order"] for b in data["banners"]] == [0, 1]
        assert all(b["image_url"] for b in data["banners"])

        db.drop_all()


def test_get_event_returns_404_for_unpublished_event():
    app = _new_app()
    with app.app_context():
        _add_event(
            title="Draft Event",
            slug="draft-event",
            published=False,
            start_datetime=NOW + timedelta(days=1),
        )

        response = app.test_client().get("/api/events/draft-event")

        assert response.status_code == 404

        db.drop_all()


def test_get_event_returns_a_draft_event_for_an_authenticated_admin():
    app = _new_app()
    with app.app_context():
        _add_event(
            title="Draft Event",
            slug="draft-event",
            published=False,
            start_datetime=NOW + timedelta(days=1),
        )
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/events/draft-event", headers=auth_header(token))
        data = response.get_json()

        assert response.status_code == 200
        assert data["title"] == "Draft Event"
        assert data["published"] is False

        db.drop_all()


def test_get_event_returns_404_for_a_draft_event_to_a_non_admin_authenticated_user():
    app = _new_app()
    with app.app_context():
        _add_event(
            title="Draft Event",
            slug="draft-event",
            published=False,
            start_datetime=NOW + timedelta(days=1),
        )
        _, token = make_user_and_token(role="volunteer")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/events/draft-event", headers=auth_header(token))

        assert response.status_code == 404

        db.drop_all()


def test_get_event_returns_404_for_unknown_slug():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/events/does-not-exist")

        assert response.status_code == 404

        db.drop_all()
