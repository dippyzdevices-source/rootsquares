"""Tests for admin users routes (23 tests), e.g. admin routes reject requests with no token; admin routes reject a volunteer role; admin routes allow a cors preflight with no auth header."""
from datetime import datetime, timezone
from unittest.mock import patch

from app import create_app
from app.auth.models import User
from app.checkin.models import EventVolunteer
from app.events.models import Event
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/users")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_volunteer_role():
    # This one really is admin-only — a volunteer must not be able to manage other volunteers.
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="volunteer")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/users", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/users", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_list_users_includes_members_and_volunteers_but_never_admins():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                User(auth_user_id="sb-1", auth_provider="supabase", email="member@example.com", role="member"),
                User(auth_user_id="sb-2", auth_provider="supabase", email="volunteer@example.com", role="volunteer"),
                User(auth_user_id="sb-3", auth_provider="supabase", email="admin2@example.com", role="admin"),
            ]
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/users", headers=_admin_headers())

        emails = {item["email"] for item in response.get_json()["items"]}
        assert emails == {"member@example.com", "volunteer@example.com"}
        db.drop_all()


def test_list_users_filters_by_search_query():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                User(auth_user_id="sb-1", auth_provider="supabase", email="priya@example.com", role="member"),
                User(auth_user_id="sb-2", auth_provider="supabase", email="rohan@example.com", role="member"),
            ]
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/users?q=rohan", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "rohan@example.com"
        db.drop_all()


def test_list_users_filters_by_role():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                User(auth_user_id="sb-1", auth_provider="supabase", email="priya@example.com", role="member"),
                User(auth_user_id="sb-2", auth_provider="supabase", email="rohan@example.com", role="volunteer"),
                User(auth_user_id="sb-3", auth_provider="supabase", email="admin2@example.com", role="admin"),
            ]
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/users?role=volunteer", headers=_admin_headers()
            )

        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "rohan@example.com"
        db.drop_all()


def test_list_users_rejects_an_unassignable_role_filter():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/users?role=admin", headers=_admin_headers()
            )

        assert response.status_code == 400
        db.drop_all()


def test_list_users_filters_by_the_linked_member_name():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        priya = User(auth_user_id="sb-1", auth_provider="supabase", email="priya@example.com", role="member")
        rohan = User(auth_user_id="sb-2", auth_provider="supabase", email="rohan@example.com", role="member")
        db.session.add_all([priya, rohan])
        db.session.commit()
        db.session.add(Member(name="Priya Das", user_id=priya.id))
        db.session.add(Member(name="Rohan Sen", user_id=rohan.id))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/users?q=Priya", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "priya@example.com"
        assert items[0]["member_name"] == "Priya Das"
        db.drop_all()


def test_list_users_shows_no_member_name_when_unlinked():
    app = _new_app()
    with app.app_context():
        db.session.add(User(auth_user_id="sb-1", auth_provider="supabase", email="priya@example.com", role="member"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/users", headers=_admin_headers())

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["member_name"] is None
        db.drop_all()


def test_update_user_role_to_volunteer_succeeds():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member")
        db.session.add(user)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/users/{user.id}", json={"role": "volunteer"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["role"] == "volunteer"
        db.session.refresh(user)
        assert user.role == "volunteer"
        db.drop_all()


def test_update_user_role_rejects_admin_as_a_target_role():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member")
        db.session.add(user)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/users/{user.id}", json={"role": "admin"}, headers=_admin_headers()
            )

        assert response.status_code == 400
        assert "role" in response.get_json()["errors"]
        db.session.refresh(user)
        assert user.role == "member"
        db.drop_all()


def test_update_user_role_refuses_to_touch_an_existing_admin():
    app = _new_app()
    with app.app_context():
        admin_user = User(auth_user_id="sb-1", auth_provider="supabase", email="admin2@example.com", role="admin")
        db.session.add(admin_user)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/users/{admin_user.id}", json={"role": "volunteer"},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        db.session.refresh(admin_user)
        assert admin_user.role == "admin"
        db.drop_all()


def test_update_user_role_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/users/999", json={"role": "volunteer"}, headers=_admin_headers()
            )
        assert response.status_code == 404
        db.drop_all()


def test_update_user_role_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member")
        db.session.add(user)
        db.session.commit()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/users/{user.id}", json={"role": "volunteer"},
                headers=auth_header(token),
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "user_role_changed"
        assert entry.target_type == "user"
        assert entry.target_id == user.id
        assert "a@b.com" in entry.description
        assert "volunteer" in entry.description
        db.drop_all()


def test_list_user_events_rejects_a_non_volunteer():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member")
        db.session.add(user)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/users/{user.id}/events", headers=_admin_headers()
            )
        assert response.status_code == 400
        db.drop_all()


def test_list_user_events_returns_all_events_and_assigned_ids():
    app = _new_app()
    with app.app_context():
        volunteer = User(auth_user_id="sb-1", auth_provider="supabase", email="v@example.com", role="volunteer")
        db.session.add(volunteer)
        event_a = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                        start_datetime=NOW)
        event_b = Event(title="Saraswati Puja 2026", slug="saraswati-puja-2026",
                        event_type="festival", start_datetime=NOW)
        db.session.add_all([event_a, event_b])
        db.session.commit()
        db.session.add(EventVolunteer(event_id=event_a.id, user_id=volunteer.id))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/users/{volunteer.id}/events", headers=_admin_headers()
            )

        assert response.status_code == 200
        data = response.get_json()
        assert {e["id"] for e in data["events"]} == {event_a.id, event_b.id}
        assert data["assigned_event_ids"] == [event_a.id]
        db.drop_all()


def test_set_user_events_replaces_the_full_assignment_set():
    app = _new_app()
    with app.app_context():
        volunteer = User(auth_user_id="sb-1", auth_provider="supabase", email="v@example.com", role="volunteer")
        db.session.add(volunteer)
        event_a = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                        start_datetime=NOW)
        event_b = Event(title="Saraswati Puja 2026", slug="saraswati-puja-2026",
                        event_type="festival", start_datetime=NOW)
        db.session.add_all([event_a, event_b])
        db.session.commit()
        db.session.add(EventVolunteer(event_id=event_a.id, user_id=volunteer.id))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().put(
                f"/api/admin/users/{volunteer.id}/events",
                json={"event_ids": [event_b.id]},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["assigned_event_ids"] == [event_b.id]
        remaining = EventVolunteer.query.filter_by(user_id=volunteer.id).all()
        assert [r.event_id for r in remaining] == [event_b.id]
        db.drop_all()


def test_set_user_events_rejects_a_non_volunteer():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com", role="member")
        db.session.add(user)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().put(
                f"/api/admin/users/{user.id}/events",
                json={"event_ids": []},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        db.drop_all()


def test_set_user_events_rejects_unknown_event_ids():
    app = _new_app()
    with app.app_context():
        volunteer = User(auth_user_id="sb-1", auth_provider="supabase", email="v@example.com", role="volunteer")
        db.session.add(volunteer)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().put(
                f"/api/admin/users/{volunteer.id}/events",
                json={"event_ids": [999]},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "event_ids" in response.get_json()["errors"]
        db.drop_all()


def test_all_users_lists_every_role_with_member_link_and_filters():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        user_a, _ = make_user_and_token(role="member", email="a@example.com")
        user_b, _ = make_user_and_token(role="volunteer", email="b@example.com")
        db.session.add(Member(user_id=user_a.id, name="Anna Roy"))
        db.session.commit()
        headers = _admin_headers()  # an admin account too
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            body = client.get("/api/admin/users/all", headers=headers).get_json()
            assert body["total"] == 3
            by_email = {u["email"]: u for u in body["items"]}
            assert by_email["a@example.com"]["member_name"] == "Anna Roy"
            assert by_email["b@example.com"]["member_name"] is None
            assert {u["role"] for u in body["items"]} == {"member", "volunteer", "admin"}
            assert all(u["first_sign_in"] for u in body["items"])

            only = client.get("/api/admin/users/all?role=volunteer,admin", headers=headers).get_json()
            assert {u["email"] for u in only["items"]} == {"b@example.com", "test@example.com"}
            found = client.get("/api/admin/users/all?q=anna", headers=headers).get_json()
            assert [u["email"] for u in found["items"]] == ["a@example.com"]
        db.drop_all()


def test_all_users_is_admin_only():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="volunteer", email="v@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            assert app.test_client().get("/api/admin/users/all", headers=auth_header(token)).status_code == 403
        db.drop_all()


def test_all_users_links_a_profile_that_matches_by_email_but_is_not_tied_yet():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        make_user_and_token(role="member", email="Late@Example.com")
        make_user_and_token(role="member", email="nobody@example.com")
        profile = Member(name="Late Signup", email="late@example.com")  # e.g. signed up at the drive, user_id still empty
        db.session.add(profile)
        db.session.commit()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            body = app.test_client().get("/api/admin/users/all", headers=_admin_headers()).get_json()
        by_email = {u["email"]: u for u in body["items"]}
        assert by_email["Late@Example.com"]["member_id"] == profile.id
        assert by_email["Late@Example.com"]["member_name"] == "Late Signup"
        assert by_email["nobody@example.com"]["member_id"] is None
        db.drop_all()


def test_admin_can_resend_a_welcome_email_and_gets_a_502_when_it_fails():
    from app.email.service import EmailServiceError

    app = _new_app()
    with app.app_context():
        user, _ = make_user_and_token(role="member", email="again@example.com")
        headers = _admin_headers()
        sent = app.extensions["email_service"].sent_emails
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            ok = client.post(f"/api/admin/users/{user.id}/welcome-email", headers=headers)
            assert ok.status_code == 200 and ok.get_json()["sent_to"] == "again@example.com"
            assert sent[-1]["to"] == "again@example.com" and sent[-1]["subject"] == "Welcome to BCA Oslo"

            assert client.post("/api/admin/users/9999/welcome-email", headers=headers).status_code == 404
            with patch.object(app.extensions["email_service"], "send_email", side_effect=EmailServiceError("boom")):
                failed = client.post(f"/api/admin/users/{user.id}/welcome-email", headers=headers)
            assert failed.status_code == 502
        db.drop_all()
