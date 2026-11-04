"""Tests for admin event duplicate (5 tests), e.g. admin routes reject requests with no token; duplicate returns 404 for unknown event; duplicate copies fields with a unique slug and resets to draft."""
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.events.models import Event, EventSession
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_event(**overrides):
    defaults = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": NOW + timedelta(days=10),
        "published": True,
        "status": "scheduled",
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        response = app.test_client().post(f"/api/admin/events/{event.id}/duplicate")
        assert response.status_code == 401
        db.drop_all()


def test_duplicate_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/events/999/duplicate", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_duplicate_copies_fields_with_a_unique_slug_and_resets_to_draft():
    app = _new_app()
    with app.app_context():
        event = _add_event(venue="Deichman Bjørvika", capacity=200)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/duplicate", headers=headers
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Durga Puja 2026"
        assert data["slug"] == "durga-puja-2026-copy"
        assert data["venue"] == "Deichman Bjørvika"
        assert data["capacity"] == 200
        assert data["published"] is False
        assert data["status"] == "scheduled"
        assert Event.query.count() == 2
        db.drop_all()


def test_duplicate_increments_the_copy_slug_when_one_already_exists():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_event(slug="durga-puja-2026-copy")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/duplicate", headers=headers
            )

        assert response.get_json()["slug"] == "durga-puja-2026-copy-2"
        db.drop_all()


def test_duplicate_copies_sessions():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        db.session.add_all(
            [
                EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Cultural Programme", sort_order=0),
                EventSession(event_id=event.id, day_label="Saturday", time=time(10, 0), title="Puja", sort_order=1),
            ]
        )
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/duplicate", headers=headers
            )

        data = response.get_json()
        assert len(data["sessions"]) == 2
        assert {s["title"] for s in data["sessions"]} == {"Cultural Programme", "Puja"}

        # The original event's own sessions are untouched, not moved.
        assert EventSession.query.filter_by(event_id=event.id).count() == 2
        assert EventSession.query.count() == 4
        db.drop_all()
