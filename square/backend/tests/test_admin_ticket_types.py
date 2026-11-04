"""Tests for admin ticket types (25 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
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


def _add_event(**overrides):
    from app.events.models import Event

    defaults = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": NOW + timedelta(days=10),
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        response = app.test_client().get(f"/api/admin/events/{event.id}/ticket-types")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/events/{event.id}/ticket-types", headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/events/1/ticket-types", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_create_ticket_type_requires_name_and_price():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types", json={}, headers=headers
            )

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"name", "price", "age_category"}
        db.drop_all()


def test_admin_create_ticket_type_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000, "capacity": 100},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Adult"
        assert data["price"] == 15000
        assert data["sold"] == 0
        db.drop_all()


def test_admin_create_ticket_type_with_a_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000, "description": "Includes dinner and entry to all sessions."},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["description"] == "Includes dinner and entry to all sessions."
        db.drop_all()


def test_admin_ticket_type_valid_on_can_be_set_changed_cleared_and_validated():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Friday - Adult", "price": 25000, "valid_on": "2026-10-23"},
                headers=headers,
            )
            assert created.status_code == 201
            assert created.get_json()["valid_on"] == "2026-10-23"
            url = f"/api/admin/ticket-types/{created.get_json()['id']}"
            changed = client.patch(url, json={"valid_on": "2026-10-24"}, headers=headers)
            assert changed.get_json()["valid_on"] == "2026-10-24"
            assert client.patch(url, json={"valid_on": "not-a-date"}, headers=headers).status_code == 400
            cleared = client.patch(url, json={"valid_on": None}, headers=headers)
            assert cleared.get_json()["valid_on"] is None
        db.drop_all()


def test_multi_day_event_requires_valid_on_but_accepts_all_days_and_rejects_other_days():
    app = _new_app()
    with app.app_context():
        event = _add_event(end_datetime=NOW + timedelta(days=12))
        headers = _admin_headers()
        day1 = (NOW + timedelta(days=10)).astimezone(ZoneInfo("Europe/Oslo")).date().isoformat()
        base = {"name": "Pass", "price": 10000, "age_category": "adult"}

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            url = f"/api/admin/events/{event.id}/ticket-types"
            missing = client.post(url, json=base, headers=headers)
            assert missing.status_code == 400 and "valid_on" in missing.get_json()["errors"]
            assert client.post(url, json={**base, "valid_on": None}, headers=headers).status_code == 201
            assert client.post(url, json={**base, "valid_on": day1}, headers=headers).status_code == 201
            outside = client.post(url, json={**base, "valid_on": "2020-01-01"}, headers=headers)
            assert outside.status_code == 400
        db.drop_all()


def test_admin_create_ticket_type_description_defaults_to_none():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000},
                headers=headers,
            )

        assert response.get_json()["description"] is None
        db.drop_all()


def test_admin_create_ticket_type_rejects_an_overly_long_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000, "description": "x" * 2001},
                headers=headers,
            )

        assert response.status_code == 400
        assert "description" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_ticket_type_description():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/ticket-types/{ticket_type.id}",
                json={"description": "VIP seating with a welcome drink."},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["description"] == "VIP seating with a welcome drink."
        db.drop_all()


def test_admin_create_ticket_type_records_the_creating_admin():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000},
                headers=auth_header(token),
            )

        data = response.get_json()
        assert data["created_by_email"] == "admin@example.com"
        assert data["updated_by_email"] == "admin@example.com"
        db.drop_all()


def test_admin_list_ticket_types_for_an_event():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        db.session.add(TicketType(event_id=event.id, name="Adult", price=15000))
        db.session.add(TicketType(event_id=event.id, name="Child", price=5000))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/events/{event.id}/ticket-types", headers=headers
            )

        assert len(response.get_json()["items"]) == 2
        db.drop_all()


def test_admin_update_ticket_type_partial():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/ticket-types/{ticket_type.id}", json={"price": 20000}, headers=headers
            )

        data = response.get_json()
        assert response.status_code == 200
        assert data["price"] == 20000
        assert data["name"] == "Adult"  # untouched by the partial update
        db.drop_all()


def test_admin_update_ticket_type_records_the_editing_admin():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        _, token = make_user_and_token(role="admin", email="editor@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/ticket-types/{ticket_type.id}", json={"price": 20000},
                headers=auth_header(token),
            )

        assert response.get_json()["updated_by_email"] == "editor@example.com"
        db.drop_all()


def test_admin_update_ticket_type_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/ticket-types/999", json={"price": 20000}, headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_ticket_type_success():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                f"/api/admin/ticket-types/{ticket_type.id}", headers=headers
            )

        assert response.status_code == 204
        assert TicketType.query.count() == 0
        db.drop_all()


def test_admin_delete_ticket_type_logs_an_audit_entry():
    from app.audit.models import AuditLog
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Durga Puja 2026", slug="durga-puja-2026")
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(
                f"/api/admin/ticket-types/{ticket_type.id}", headers=auth_header(token)
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "ticket_type_deleted"
        assert entry.target_type == "ticket_type"
        assert entry.target_id == ticket_type.id
        assert "Adult" in entry.description
        assert "Durga Puja 2026" in entry.description
        db.drop_all()


def test_admin_create_ticket_type_requires_an_age_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "VIP", "price": 15000},
                headers=headers,
            )

        assert response.get_json()["age_category"] == "other"
        db.drop_all()


def test_admin_create_ticket_type_accepts_an_age_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000, "age_category": "adult"},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["age_category"] == "adult"
        db.drop_all()


def test_admin_create_ticket_type_rejects_an_invalid_age_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000, "age_category": "teenager"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "age_category" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_ticket_type_age_category():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Child", price=5000)
        db.session.add(ticket_type)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/ticket-types/{ticket_type.id}",
                json={"age_category": "child"},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["age_category"] == "child"
        db.drop_all()


def test_admin_create_ticket_type_coupon_eligible_defaults_to_true():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "Adult", "price": 15000},
                headers=headers,
            )

        assert response.get_json()["coupon_eligible"] is True
        db.drop_all()


def test_admin_create_ticket_type_can_be_marked_coupon_ineligible():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/ticket-types",
                json={"age_category": "other", "name": "VIP", "price": 50000, "coupon_eligible": False},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["coupon_eligible"] is False
        db.drop_all()


def test_admin_update_ticket_type_coupon_eligible_rejects_a_non_boolean():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/ticket-types/{ticket_type.id}",
                json={"coupon_eligible": "nope"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "coupon_eligible" in response.get_json()["errors"]
        db.drop_all()
