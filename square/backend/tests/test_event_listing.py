"""Tests for event listing (9 tests), e.g. list events returns only published upcoming events by default; list events includes drafts for an authenticated admin; list events excludes drafts for a non admin authenticated user."""
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


def test_list_events_returns_only_published_upcoming_events_by_default():
    app = _new_app()
    with app.app_context():
        _add_event(title="Upcoming Published", slug="upcoming-published", start_datetime=NOW + timedelta(days=1))
        _add_event(
            title="Upcoming Unpublished",
            slug="upcoming-unpublished",
            start_datetime=NOW + timedelta(days=1),
            published=False,
        )
        _add_event(title="Past Published", slug="past-published", start_datetime=NOW - timedelta(days=1))

        response = app.test_client().get("/api/events")
        data = response.get_json()

        assert response.status_code == 200
        assert [item["title"] for item in data["items"]] == ["Upcoming Published"]
        assert data["items"][0]["published"] is True

        db.drop_all()


def test_list_events_includes_drafts_for_an_authenticated_admin():
    app = _new_app()
    with app.app_context():
        _add_event(title="Upcoming Published", slug="upcoming-published", start_datetime=NOW + timedelta(days=1))
        _add_event(
            title="Upcoming Unpublished",
            slug="upcoming-unpublished",
            start_datetime=NOW + timedelta(days=1),
            published=False,
        )
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/events", headers=auth_header(token))
        data = response.get_json()

        assert response.status_code == 200
        titles = {item["title"]: item["published"] for item in data["items"]}
        assert titles == {"Upcoming Published": True, "Upcoming Unpublished": False}

        db.drop_all()


def test_list_events_excludes_drafts_for_a_non_admin_authenticated_user():
    app = _new_app()
    with app.app_context():
        _add_event(title="Upcoming Published", slug="upcoming-published", start_datetime=NOW + timedelta(days=1))
        _add_event(
            title="Upcoming Unpublished",
            slug="upcoming-unpublished",
            start_datetime=NOW + timedelta(days=1),
            published=False,
        )
        _, token = make_user_and_token(role="member")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/events", headers=auth_header(token))
        data = response.get_json()

        assert response.status_code == 200
        assert [item["title"] for item in data["items"]] == ["Upcoming Published"]

        db.drop_all()


def test_list_events_filters_by_type():
    app = _new_app()
    with app.app_context():
        _add_event(
            title="Festival Event",
            slug="festival-event",
            event_type="festival",
            start_datetime=NOW + timedelta(days=1),
        )
        _add_event(
            title="Cultural Event",
            slug="cultural-event",
            event_type="cultural",
            start_datetime=NOW + timedelta(days=1),
        )

        data = app.test_client().get("/api/events?type=cultural").get_json()

        assert [item["title"] for item in data["items"]] == ["Cultural Event"]

        db.drop_all()


def test_list_events_when_past_returns_past_events_only():
    app = _new_app()
    with app.app_context():
        _add_event(title="Past Event", slug="past-event", start_datetime=NOW - timedelta(days=2))
        _add_event(title="Future Event", slug="future-event", start_datetime=NOW + timedelta(days=2))

        data = app.test_client().get("/api/events?when=past").get_json()

        assert [item["title"] for item in data["items"]] == ["Past Event"]

        db.drop_all()


def test_list_events_orders_upcoming_soonest_first():
    app = _new_app()
    with app.app_context():
        _add_event(title="Later", slug="later", start_datetime=NOW + timedelta(days=10))
        _add_event(title="Sooner", slug="sooner", start_datetime=NOW + timedelta(days=1))

        data = app.test_client().get("/api/events").get_json()

        assert [item["title"] for item in data["items"]] == ["Sooner", "Later"]

        db.drop_all()


def test_list_events_paginates():
    app = _new_app()
    with app.app_context():
        for i in range(3):
            _add_event(title=f"Event {i}", slug=f"event-{i}", start_datetime=NOW + timedelta(days=i + 1))

        client = app.test_client()
        first_page = client.get("/api/events?per_page=2&page=1").get_json()
        second_page = client.get("/api/events?per_page=2&page=2").get_json()

        assert len(first_page["items"]) == 2
        assert first_page["total"] == 3
        assert first_page["total_pages"] == 2
        assert len(second_page["items"]) == 1

        db.drop_all()


def test_list_events_rejects_invalid_when():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/events?when=sideways")

        assert response.status_code == 400

        db.drop_all()


def test_list_events_rejects_invalid_type():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/events?type=bogus")

        assert response.status_code == 400

        db.drop_all()
