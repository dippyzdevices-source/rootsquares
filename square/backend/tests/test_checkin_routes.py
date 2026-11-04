"""Tests for checkin routes (18 tests), e.g. scan requires a token; scan rejects a member role; scan allows a volunteer role assigned to the ticket s event."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.checkin.models import EventVolunteer
from app.extensions import db
from app.events.models import Event
from app.members.models import Member
from app.orders.models import Order, OrderItem
from app.tickets.models import Ticket, TicketType
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


def _volunteer_headers():
    _, token = make_user_and_token(role="volunteer", email="volunteer@example.com")
    return auth_header(token)


def _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026", status="valid",
                ticket_code="abc123", start_datetime=NOW, end_datetime=None):
    event = Event(title=event_title, slug=event_slug, event_type="festival",
                  start_datetime=start_datetime, end_datetime=end_datetime)
    db.session.add(event)
    db.session.commit()
    ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
    db.session.add(ticket_type)
    db.session.commit()
    order = Order(order_number=f"BCA-2026-{event.id:06d}", event_id=event.id,
                  customer_name="Priya Das", customer_email="priya@example.com",
                  total_amount=15000)
    db.session.add(order)
    db.session.commit()
    item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                     unit_price=15000, subtotal=15000)
    db.session.add(item)
    db.session.commit()
    ticket = Ticket(order_item_id=item.id, ticket_code=ticket_code, status=status)
    db.session.add(ticket)
    db.session.commit()
    return event, ticket


def test_scan_requires_a_token():
    app = _new_app()
    with app.app_context():
        _add_ticket()
        response = app.test_client().post("/api/admin/checkin/scan", json={})
        assert response.status_code == 401
        db.drop_all()


def test_scan_rejects_a_member_role():
    app = _new_app()
    with app.app_context():
        _add_ticket()
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan", json={}, headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_scan_allows_a_volunteer_role_assigned_to_the_ticket_s_event():
    app = _new_app()
    with app.app_context():
        event, ticket = _add_ticket()
        volunteer, token = make_user_and_token(role="volunteer", email="volunteer@example.com")
        db.session.add(EventVolunteer(event_id=event.id, user_id=volunteer.id))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=auth_header(token),
            )
        assert response.status_code == 200
        assert response.get_json()["result"] == "valid"
        db.drop_all()


def test_scan_reports_not_assigned_for_a_volunteer_not_assigned_to_the_ticket_s_event():
    app = _new_app()
    with app.app_context():
        event, ticket = _add_ticket()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=_volunteer_headers(),
            )
        # Not a hard 403 — an unassigned volunteer scanning a real ticket is a business
        # outcome the door needs to see and act on, same as invalid/already_used.
        assert response.status_code == 200
        data = response.get_json()
        assert data["result"] == "not_assigned"
        assert data["event_title"] == "Durga Puja 2026"
        db.drop_all()


def test_summary_scopes_to_assigned_events_for_a_volunteer():
    app = _new_app()
    with app.app_context():
        assigned_event, _ = _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026",
                                        ticket_code="abc123")
        _add_ticket(event_title="Saraswati Puja 2026", event_slug="saraswati-puja-2026",
                   ticket_code="def456")

        volunteer, token = make_user_and_token(role="volunteer", email="volunteer@example.com")
        db.session.add(EventVolunteer(event_id=assigned_event.id, user_id=volunteer.id))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/checkin/summary", headers=auth_header(token)
            )

        assert response.status_code == 200
        # Only the assigned event's one ticket is counted, not the other event's.
        assert response.get_json() == {"total_tickets": 1, "checked_in_count": 0}
        db.drop_all()


def test_summary_counts_every_event_for_an_admin():
    app = _new_app()
    with app.app_context():
        _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026", ticket_code="abc123")
        _add_ticket(event_title="Saraswati Puja 2026", event_slug="saraswati-puja-2026", ticket_code="def456")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/checkin/summary", headers=_admin_headers()
            )

        assert response.status_code == 200
        assert response.get_json() == {"total_tickets": 2, "checked_in_count": 0}
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/checkin/scan", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_scan_returns_invalid_for_an_unknown_code():
    app = _new_app()
    with app.app_context():
        _add_ticket()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": "does-not-exist"},
                headers=_admin_headers(),
            )
        assert response.status_code == 200
        assert response.get_json() == {"result": "invalid"}
        db.drop_all()


def test_scan_succeeds_and_stamps_who_and_when_and_auto_detects_the_event():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket()
        admin_user, token = make_user_and_token(role="admin", email="door@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=auth_header(token),
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["result"] == "valid"
        assert data["customer_name"] == "Priya Das"
        assert data["ticket_type"] == "Adult"
        # The event is read straight off the ticket — no event was selected up front.
        assert data["event_title"] == "Durga Puja 2026"

        db.session.refresh(ticket)
        assert ticket.status == "used"
        assert ticket.checked_in_at is not None
        assert ticket.checked_in_by_user_id == admin_user.id
        db.drop_all()


def test_scan_reports_already_used_on_a_second_scan():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            first = client.post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=headers,
            )
            assert first.get_json()["result"] == "valid"

            second = client.post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=headers,
            )

        assert second.status_code == 200
        data = second.get_json()
        assert data["result"] == "already_used"
        assert data["checked_in_at"] is not None
        assert data["customer_name"] == "Priya Das"
        db.drop_all()


def test_scan_reports_voided_for_a_ticket_on_a_cancelled_order():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket(status="void")
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=headers,
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["result"] == "voided"
        assert data["customer_name"] == "Priya Das"
        assert db.session.get(Ticket, ticket.id).status == "void"  # scanning never flips it to "used"
        db.drop_all()


def test_checkin_summary_excludes_voided_tickets_from_the_total():
    app = _new_app()
    with app.app_context():
        _add_ticket(event_slug="durga-puja-2026", ticket_code="valid-1")
        _add_ticket(event_slug="saraswati-puja-2026", ticket_code="void-1", status="void")
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/checkin/summary", headers=headers)

        assert response.get_json() == {"total_tickets": 1, "checked_in_count": 0}
        db.drop_all()


def test_scan_from_two_different_events_each_auto_detect_their_own_event():
    # Without a pre-selected event, an admin scanning tickets from two different events back
    # to back must get each ticket's own real event, not get treated as "wrong event".
    app = _new_app()
    with app.app_context():
        _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026", ticket_code="abc123")
        _add_ticket(event_title="Saraswati Puja 2026", event_slug="saraswati-puja-2026", ticket_code="def456")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            first = client.post("/api/admin/checkin/scan", json={"ticket_code": "abc123"}, headers=headers)
            second = client.post("/api/admin/checkin/scan", json={"ticket_code": "def456"}, headers=headers)

        assert first.get_json() == {
            "result": "valid", "customer_name": "Priya Das", "ticket_type": "Adult",
            "event_title": "Durga Puja 2026",
        }
        assert second.get_json() == {
            "result": "valid", "customer_name": "Priya Das", "ticket_type": "Adult",
            "event_title": "Saraswati Puja 2026",
        }
        db.drop_all()


def test_scan_reports_already_used_with_the_scanning_volunteer_s_member_name():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket()
        admin_user, token = make_user_and_token(role="admin", email="door@example.com")
        db.session.add(Member(user_id=admin_user.id, name="Door Volunteer"))
        db.session.commit()
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post(
                "/api/admin/checkin/scan", json={"ticket_code": ticket.ticket_code}, headers=headers
            )
            second = client.post(
                "/api/admin/checkin/scan", json={"ticket_code": ticket.ticket_code}, headers=headers
            )

        data = second.get_json()
        assert data["checked_in_by"] == "door@example.com"
        assert data["checked_in_by_name"] == "Door Volunteer"
        db.drop_all()


def test_scan_reports_pre_event_before_the_event_starts():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket(start_datetime=NOW + timedelta(days=3))
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=_admin_headers(),
            )
        assert response.status_code == 200
        data = response.get_json()
        assert data["result"] == "pre_event"
        assert data["customer_name"] == "Priya Das"
        assert data["ticket_type"] == "Adult"
        assert "event_start_date" in data
        db.session.refresh(ticket)
        assert ticket.status == "valid"  # not marked used
        db.drop_all()


def test_scan_reports_post_event_after_the_event_ends():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket(
            start_datetime=NOW - timedelta(days=5),
            end_datetime=NOW - timedelta(days=3),
        )
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=_admin_headers(),
            )
        assert response.status_code == 200
        data = response.get_json()
        assert data["result"] == "post_event"
        assert data["customer_name"] == "Priya Das"
        assert "event_end_date" in data
        db.session.refresh(ticket)
        assert ticket.status == "valid"  # not marked used
        db.drop_all()


def test_scan_reports_already_used_even_after_the_event_has_ended():
    app = _new_app()
    with app.app_context():
        _, ticket = _add_ticket(
            status="used",
            start_datetime=NOW - timedelta(days=5),
            end_datetime=NOW - timedelta(days=3),
        )
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/checkin/scan",
                json={"ticket_code": ticket.ticket_code},
                headers=_admin_headers(),
            )
        assert response.status_code == 200
        assert response.get_json()["result"] == "already_used"
        db.drop_all()


def test_summary_counts_total_and_checked_in_tickets():
    app = _new_app()
    with app.app_context():
        event, ticket = _add_ticket()
        ticket_type = TicketType.query.filter_by(event_id=event.id).one()
        order = Order.query.filter_by(event_id=event.id).one()
        item2 = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                          unit_price=15000, subtotal=15000)
        db.session.add(item2)
        db.session.commit()
        db.session.add(Ticket(order_item_id=item2.id, ticket_code="def456", status="valid"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            client.post("/api/admin/checkin/scan", json={"ticket_code": "abc123"}, headers=headers)
            response = client.get("/api/admin/checkin/summary", headers=headers)

        assert response.status_code == 200
        assert response.get_json() == {"total_tickets": 2, "checked_in_count": 1}
        db.drop_all()
