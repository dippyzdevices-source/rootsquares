"""Tests for admin event task assignments (12 tests), e.g. admin routes reject requests with no token; admin create task assignment requires fields; admin create task assignment returns 404 for unknown event."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.events.models import Event, EventTaskAssignment
from app.extensions import db
from app.members.models import Member
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


def _add_member(name="Priya Das"):
    member = Member(name=name)
    db.session.add(member)
    db.session.commit()
    return member


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        response = app.test_client().post(f"/api/admin/events/{event.id}/task-assignments", json={})
        assert response.status_code == 401
        db.drop_all()


def test_admin_create_task_assignment_requires_fields():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/task-assignments", json={}, headers=headers
            )

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"member_id", "category"}
        db.drop_all()


def test_admin_create_task_assignment_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        member = _add_member()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events/999/task-assignments",
                json={"member_id": member.id, "category": "food"},
                headers=headers,
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_create_task_assignment_rejects_an_unknown_member():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/task-assignments",
                json={"member_id": 999, "category": "food"},
                headers=headers,
            )
        assert response.status_code == 400
        assert "member_id" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_task_assignment_rejects_an_invalid_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/task-assignments",
                json={"member_id": member.id, "category": "not-a-category"},
                headers=headers,
            )
        assert response.status_code == 400
        assert "category" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_task_assignment_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/task-assignments",
                json={"member_id": member.id, "category": "food"},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["member_id"] == member.id
        assert data["member_name"] == "Priya Das"
        assert data["category"] == "food"
        assert EventTaskAssignment.query.filter_by(event_id=event.id).count() == 1
        db.drop_all()


def test_event_detail_includes_task_assignments():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        db.session.add(EventTaskAssignment(event_id=event.id, member_id=member.id, category="decoration"))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(f"/api/admin/events/{event.id}", headers=headers)

        data = response.get_json()
        assert len(data["task_assignments"]) == 1
        assert data["task_assignments"][0]["category"] == "decoration"
        assert data["task_assignments"][0]["member_name"] == "Priya Das"
        db.drop_all()


def test_task_assignment_includes_member_email_preferring_linked_user():
    app = _new_app()
    with app.app_context():
        event = _add_event()

        user, _ = make_user_and_token(email="priya@example.com")
        linked_member = Member(user_id=user.id, name="Priya Das", email="imported-address@example.com")
        unlinked_member = Member(name="Rohan Sen", email="rohan@example.com")
        db.session.add_all([linked_member, unlinked_member])
        db.session.commit()

        db.session.add(EventTaskAssignment(event_id=event.id, member_id=linked_member.id, category="food"))
        db.session.add(EventTaskAssignment(event_id=event.id, member_id=unlinked_member.id, category="decoration"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(f"/api/admin/events/{event.id}", headers=_admin_headers())

        by_member = {a["member_name"]: a["member_email"] for a in response.get_json()["task_assignments"]}
        assert by_member["Priya Das"] == "priya@example.com"
        assert by_member["Rohan Sen"] == "rohan@example.com"
        db.drop_all()


def test_admin_update_task_assignment_changes_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        assignment = EventTaskAssignment(event_id=event.id, member_id=member.id, category="food")
        db.session.add(assignment)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event.id}/task-assignments/{assignment.id}",
                json={"category": "logistics"},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["category"] == "logistics"
        db.drop_all()


def test_admin_update_task_assignment_returns_404_for_an_assignment_on_a_different_event():
    app = _new_app()
    with app.app_context():
        event_a = _add_event(slug="event-a")
        event_b = _add_event(slug="event-b")
        member = _add_member()
        assignment = EventTaskAssignment(event_id=event_a.id, member_id=member.id, category="food")
        db.session.add(assignment)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event_b.id}/task-assignments/{assignment.id}",
                json={"category": "logistics"},
                headers=headers,
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_task_assignment_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        assignment = EventTaskAssignment(event_id=event.id, member_id=member.id, category="food")
        db.session.add(assignment)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                f"/api/admin/events/{event.id}/task-assignments/{assignment.id}", headers=headers
            )

        assert response.status_code == 204
        assert EventTaskAssignment.query.count() == 0
        db.drop_all()


def test_deleting_an_event_cascades_to_its_task_assignments():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        member = _add_member()
        db.session.add(EventTaskAssignment(event_id=event.id, member_id=member.id, category="food"))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(f"/api/admin/events/{event.id}", headers=headers)

        assert EventTaskAssignment.query.count() == 0
        db.drop_all()
