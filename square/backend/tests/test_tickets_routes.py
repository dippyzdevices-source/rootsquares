"""Tests for tickets routes (11 tests), e.g. list ticket types requires event id; list ticket types returns 404 for an unpublished event; list ticket types includes an unpublished event for an authenticated a."""
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


def _add_event(**overrides):
    from app.events.models import Event

    defaults = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": NOW + timedelta(days=10),
        "published": True,
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _add_type(event_id, **overrides):
    from app.tickets.models import TicketType

    defaults = {"event_id": event_id, "name": "Adult", "price": 15000}
    defaults.update(overrides)
    ticket_type = TicketType(**defaults)
    db.session.add(ticket_type)
    db.session.commit()
    return ticket_type


def test_list_ticket_types_requires_event_id():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/tickets/types")
        assert response.status_code == 400
        db.drop_all()


def test_list_ticket_types_returns_404_for_an_unpublished_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        assert response.status_code == 404
        db.drop_all()


def test_list_ticket_types_includes_an_unpublished_event_for_an_authenticated_admin():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        _add_type(event.id, name="Adult")
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/tickets/types?event_id={event.id}", headers=auth_header(token)
            )

        assert response.status_code == 200
        assert [t["name"] for t in response.get_json()["items"]] == ["Adult"]
        db.drop_all()


def test_list_ticket_types_still_returns_404_for_a_non_admin_authenticated_user():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        _, token = make_user_and_token(role="member")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/tickets/types?event_id={event.id}", headers=auth_header(token)
            )

        assert response.status_code == 404
        db.drop_all()


def test_list_ticket_types_marks_a_future_sale_start_as_upcoming():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id, sale_start=NOW + timedelta(days=1))

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["status"] == "upcoming"
        db.drop_all()


def test_list_ticket_types_marks_a_past_sale_end_as_ended():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id, sale_end=NOW - timedelta(days=1))

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["status"] == "ended"
        db.drop_all()


def test_list_ticket_types_marks_a_full_capacity_as_sold_out():
    from app.orders.models import Order, OrderItem

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, capacity=2)
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=30000, payment_status="paid")
        db.session.add(order)
        db.session.commit()
        db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=2,
                                 unit_price=15000, subtotal=30000))
        db.session.commit()

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["status"] == "sold_out"
        assert data["items"][0]["remaining"] == 0
        db.drop_all()


def test_list_ticket_types_defaults_to_on_sale_with_no_constraints():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id)

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["status"] == "on_sale"
        assert data["items"][0]["remaining"] is None
        db.drop_all()


def test_list_ticket_types_includes_description():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id, description="Includes dinner and entry to all sessions.")

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["description"] == "Includes dinner and entry to all sessions."
        db.drop_all()


def test_list_ticket_types_includes_age_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id, age_category="child")

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["age_category"] == "child"
        db.drop_all()


def test_list_ticket_types_includes_coupon_eligible():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_type(event.id, coupon_eligible=False)

        response = app.test_client().get(f"/api/tickets/types?event_id={event.id}")
        data = response.get_json()

        assert data["items"][0]["coupon_eligible"] is False
        db.drop_all()
