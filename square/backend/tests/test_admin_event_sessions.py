"""Tests for admin event sessions (13 tests), e.g. admin routes reject requests with no token; admin create session requires fields; admin create session returns 404 for unknown event."""
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
        "published": False,
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
        response = app.test_client().post(f"/api/admin/events/{event.id}/sessions", json={})
        assert response.status_code == 401
        db.drop_all()


def test_admin_create_session_requires_fields():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/sessions", json={}, headers=headers
            )

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"day_label", "time", "title"}
        db.drop_all()


def test_admin_create_session_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events/999/sessions",
                json={"day_label": "Friday", "time": "18:00", "title": "Cultural Programme"},
                headers=headers,
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_create_session_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/sessions",
                json={"day_label": "Friday", "time": "18:00", "title": "Cultural Programme"},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["day_label"] == "Friday"
        assert data["time"] == "18:00"
        assert data["title"] == "Cultural Programme"
        assert data["description"] is None
        assert EventSession.query.filter_by(event_id=event.id).count() == 1
        db.drop_all()


def test_admin_create_session_with_a_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/sessions",
                json={
                    "day_label": "Friday",
                    "time": "18:00",
                    "title": "Cultural Programme",
                    "description": "Traditional dance and music performances.",
                },
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["description"] == "Traditional dance and music performances."
        db.drop_all()


def test_admin_create_session_rejects_an_overly_long_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/sessions",
                json={"day_label": "Friday", "time": "18:00", "title": "Cultural Programme", "description": "x" * 2001},
                headers=headers,
            )

        assert response.status_code == 400
        assert "description" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_session_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        session = EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Cultural Programme")
        db.session.add(session)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event.id}/sessions/{session.id}",
                json={"description": "Doors open 30 minutes early."},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["description"] == "Doors open 30 minutes early."
        db.drop_all()


def test_admin_create_session_rejects_an_invalid_time():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/sessions",
                json={"day_label": "Friday", "time": "not-a-time", "title": "Cultural Programme"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "time" in response.get_json()["errors"]
        db.drop_all()


def test_event_detail_includes_sessions_ordered_by_sort_order():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=True)
        db.session.add_all(
            [
                EventSession(event_id=event.id, day_label="Saturday", time=time(10, 0), title="Puja", sort_order=2),
                EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Cultural Programme", sort_order=1),
            ]
        )
        db.session.commit()

        response = app.test_client().get(f"/api/events/{event.slug}")
        data = response.get_json()

        assert [s["title"] for s in data["sessions"]] == ["Cultural Programme", "Puja"]
        db.drop_all()


def test_admin_update_session_success_and_partial():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        session = EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Cultural Programme")
        db.session.add(session)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event.id}/sessions/{session.id}",
                json={"time": "19:00"},
                headers=headers,
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["time"] == "19:00"
        assert data["title"] == "Cultural Programme"  # untouched by a partial update
        db.drop_all()


def test_admin_update_session_returns_404_for_a_session_on_a_different_event():
    app = _new_app()
    with app.app_context():
        event_a = _add_event(slug="event-a")
        event_b = _add_event(slug="event-b")
        session = EventSession(event_id=event_a.id, day_label="Friday", time=time(18, 0), title="Programme")
        db.session.add(session)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event_b.id}/sessions/{session.id}",
                json={"time": "19:00"},
                headers=headers,
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_session_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        session = EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Programme")
        db.session.add(session)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                f"/api/admin/events/{event.id}/sessions/{session.id}", headers=headers
            )

        assert response.status_code == 204
        assert EventSession.query.count() == 0
        db.drop_all()


def test_deleting_an_event_cascades_to_its_sessions():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        db.session.add(EventSession(event_id=event.id, day_label="Friday", time=time(18, 0), title="Programme"))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(f"/api/admin/events/{event.id}", headers=headers)

        assert EventSession.query.count() == 0
        db.drop_all()
