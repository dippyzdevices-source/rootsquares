"""Tests for coupons public (13 tests), e.g. validate coupon requires event id and code; validate coupon returns 404 for an unpublished event; validate coupon works for an unpublished event when authenticated as a."""
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


def _add_coupon(event_id, **overrides):
    from app.coupons.models import Coupon

    defaults = {"event_id": event_id, "code": "SAVE20", "discount_percent": 20}
    defaults.update(overrides)
    coupon = Coupon(**defaults)
    db.session.add(coupon)
    db.session.commit()
    return coupon


def test_validate_coupon_requires_event_id_and_code():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/coupons/validate")
        assert response.status_code == 400
        db.drop_all()


def test_validate_coupon_returns_404_for_an_unpublished_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )
        assert response.status_code == 404
        db.drop_all()


def test_validate_coupon_works_for_an_unpublished_event_when_authenticated_as_admin():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        _add_coupon(event.id)
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/coupons/validate?event_id={event.id}&code=SAVE20",
                headers=auth_header(token),
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["valid"] is True
        assert data["code"] == "SAVE20"
        db.drop_all()


def test_validate_coupon_still_returns_404_for_a_non_admin_authenticated_user():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        _add_coupon(event.id)
        _, token = make_user_and_token(role="member")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/coupons/validate?event_id={event.id}&code=SAVE20",
                headers=auth_header(token),
            )

        assert response.status_code == 404
        db.drop_all()


def test_validate_coupon_success_is_case_insensitive():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id, code="SAVE20", discount_percent=20)

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=save20"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["valid"] is True
        assert data["discount_percent"] == 20
        assert data["code"] == "SAVE20"
        db.drop_all()


def test_validate_coupon_rejects_an_unknown_code():
    app = _new_app()
    with app.app_context():
        event = _add_event()

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=NOPE"
        )

        assert response.status_code == 200
        assert response.get_json()["valid"] is False
        db.drop_all()


def test_validate_coupon_rejects_an_inactive_code():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id, is_active=False)

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.status_code == 200
        assert response.get_json()["valid"] is False
        db.drop_all()


def test_validate_coupon_rejects_a_code_from_a_different_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        _add_coupon(other_event.id)

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.status_code == 200
        assert response.get_json()["valid"] is False
        db.drop_all()


def test_validate_coupon_includes_an_empty_ticket_type_restriction_by_default():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id)

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.get_json()["allowed_ticket_type_ids"] == []
        db.drop_all()


def test_validate_coupon_includes_the_ticket_type_restriction_when_set():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(adult)
        db.session.commit()
        _add_coupon(event.id, allowed_ticket_type_ids=str(adult.id))

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.get_json()["allowed_ticket_type_ids"] == [adult.id]
        db.drop_all()


def test_validate_coupon_returns_null_remaining_redemptions_when_unlimited():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id)  # max_redemptions defaults to None

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.get_json()["remaining_redemptions"] is None
        db.drop_all()


def test_validate_coupon_returns_remaining_redemptions_when_capped():
    """This is the field the checkout page now uses to warn BEFORE submit, rather than only
    showing a false "applied"/"free" preview that checkout's own hard gate then rejects."""
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(adult)
        coupon = _add_coupon(event.id, max_redemptions=5)
        db.session.commit()

        paid_order = Order(
            order_number="BCA-2026-000001",
            event_id=event.id,
            customer_name="Priya Das",
            customer_email="priya@example.com",
            total_amount=0,
            coupon_id=coupon.id,
            coupon_code=coupon.code,
            payment_status="paid",
        )
        db.session.add(paid_order)
        db.session.flush()
        item = OrderItem(
            order_id=paid_order.id, ticket_type_id=adult.id, quantity=3, unit_price=15000, subtotal=0
        )
        db.session.add(item)
        db.session.flush()
        db.session.add_all([Ticket(order_item_id=item.id, ticket_code=f"t{i}") for i in range(3)])
        db.session.commit()

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.get_json()["remaining_redemptions"] == 2  # 5 - 3
        db.drop_all()


def test_validate_coupon_never_returns_a_negative_remaining_redemptions():
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(adult)
        # Still is_active=True here — max_redemptions was raised or reached exactly as this
        # order landed, before deactivate_coupon_if_limit_reached() got a chance to flip it.
        coupon = _add_coupon(event.id, max_redemptions=1)
        db.session.commit()

        paid_order = Order(
            order_number="BCA-2026-000001",
            event_id=event.id,
            customer_name="Priya Das",
            customer_email="priya@example.com",
            total_amount=0,
            coupon_id=coupon.id,
            coupon_code=coupon.code,
            payment_status="paid",
        )
        db.session.add(paid_order)
        db.session.flush()
        item = OrderItem(
            order_id=paid_order.id, ticket_type_id=adult.id, quantity=3, unit_price=15000, subtotal=0
        )
        db.session.add(item)
        db.session.flush()
        db.session.add_all([Ticket(order_item_id=item.id, ticket_code=f"t{i}") for i in range(3)])
        db.session.commit()

        response = app.test_client().get(
            f"/api/coupons/validate?event_id={event.id}&code=SAVE20"
        )

        assert response.get_json()["remaining_redemptions"] == 0  # not -2
        db.drop_all()
