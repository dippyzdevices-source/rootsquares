"""Tests for orders lookup (6 tests), e.g. lookup returns the order for a matching order number and email; lookup returns 404 for a mismatched email; lookup returns 404 for an unknown order number."""
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


def _checkout(client, event, ticket_type):
    payload = {
        "event_id": event.id,
        "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}],
        "customer_name": "Priya Das",
        "customer_email": "priya@example.com",
        "customer_phone": "41234567",
    }
    return client.post("/api/orders", json=payload)


def test_lookup_returns_the_order_for_a_matching_order_number_and_email():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        created = _checkout(client, event, ticket_type).get_json()

        response = client.get(
            f"/api/orders/lookup?order_number={created['order_number']}&email=priya@example.com"
        )

        assert response.status_code == 200
        assert response.get_json()["order_number"] == created["order_number"]
        db.drop_all()


def test_lookup_returns_404_for_a_mismatched_email():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        created = _checkout(client, event, ticket_type).get_json()

        response = client.get(
            f"/api/orders/lookup?order_number={created['order_number']}&email=wrong@example.com"
        )

        assert response.status_code == 404
        db.drop_all()


def test_lookup_returns_404_for_an_unknown_order_number():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get(
            "/api/orders/lookup?order_number=BCA-2026-999999&email=priya@example.com"
        )
        assert response.status_code == 404
        db.drop_all()


def test_my_orders_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/orders/me")
        assert response.status_code == 401
        db.drop_all()


def test_my_orders_returns_only_the_authenticated_users_orders():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        user, token = make_user_and_token(email="priya@example.com")
        client = app.test_client()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client.post(
                "/api/orders",
                json={
                    "event_id": event.id,
                    "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}],
                    "customer_name": "Priya Das",
                    "customer_email": "priya@example.com",
                    "customer_phone": "41234567",
                },
                headers=auth_header(token),
            )
            # A guest order placed before registering, with the same email, DOES show up.
            client.post(
                "/api/orders",
                json={
                    "event_id": event.id,
                    "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}],
                    "customer_name": "Priya Das",
                    "customer_email": "priya@example.com",
                    "customer_phone": "41234567",
                },
            )

            response = client.get("/api/orders/me", headers=auth_header(token))

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        db.drop_all()


def test_my_orders_excludes_other_emails_guest_orders():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        user, token = make_user_and_token(email="someone@example.com")
        client = app.test_client()
        _checkout(client, event, ticket_type)  # guest order for priya@example.com

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.get("/api/orders/me", headers=auth_header(token))

        assert response.get_json()["items"] == []
        db.drop_all()
