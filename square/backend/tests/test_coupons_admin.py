"""Tests for coupons admin (23 tests), e.g. admin coupon routes reject requests with no token; admin coupon routes reject a non admin role; admin create coupon requires code and discount percent."""
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


def _add_coupon(event_id, **overrides):
    from app.coupons.models import Coupon

    defaults = {"event_id": event_id, "code": "SAVE20", "discount_percent": 20}
    defaults.update(overrides)
    coupon = Coupon(**defaults)
    db.session.add(coupon)
    db.session.commit()
    return coupon


def _add_type(event_id, **overrides):
    from app.tickets.models import TicketType

    defaults = {"event_id": event_id, "name": "Adult", "price": 15000}
    defaults.update(overrides)
    ticket_type = TicketType(**defaults)
    db.session.add(ticket_type)
    db.session.commit()
    return ticket_type


def test_admin_coupon_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        response = app.test_client().get(f"/api/admin/events/{event.id}/coupons")
        assert response.status_code == 401
        db.drop_all()


def test_admin_coupon_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/events/{event.id}/coupons", headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_create_coupon_requires_code_and_discount_percent():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons", json={}, headers=headers
            )

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"code", "discount_percent"}
        db.drop_all()


def test_admin_create_coupon_success():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "save20", "discount_percent": 20},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        # Stored/returned upper-cased regardless of the casing an admin typed.
        assert data["code"] == "SAVE20"
        assert data["discount_percent"] == 20
        assert data["is_active"] is True
        db.drop_all()


def test_admin_create_coupon_allows_100_percent_discount():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "FREE100", "discount_percent": 100},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["discount_percent"] == 100
        db.drop_all()


def test_admin_create_coupon_rejects_a_discount_over_100():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "TOOMUCH", "discount_percent": 150},
                headers=headers,
            )

        assert response.status_code == 400
        assert "discount_percent" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_coupon_rejects_a_duplicate_code_for_the_same_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id, code="SAVE20")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "save20", "discount_percent": 10},
                headers=headers,
            )

        assert response.status_code == 400
        assert "code" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_coupon_allows_the_same_code_on_a_different_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        _add_coupon(event.id, code="SAVE20")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{other_event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 10},
                headers=headers,
            )

        assert response.status_code == 201
        db.drop_all()


def test_admin_list_coupons():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_coupon(event.id, code="SAVE20")
        _add_coupon(event.id, code="FREE100", discount_percent=100)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/events/{event.id}/coupons", headers=headers
            )

        assert response.status_code == 200
        assert len(response.get_json()["items"]) == 2
        db.drop_all()


def test_admin_update_coupon_can_deactivate_it():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        coupon = _add_coupon(event.id)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/coupons/{coupon.id}", json={"is_active": False}, headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["is_active"] is False
        db.drop_all()


def test_admin_update_coupon_404s_for_an_unknown_coupon():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/coupons/999", json={"is_active": False}, headers=headers
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_create_coupon_defaults_to_no_ticket_type_restriction():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20},
                headers=headers,
            )

        assert response.get_json()["allowed_ticket_type_ids"] == []
        db.drop_all()


def test_admin_create_coupon_with_a_ticket_type_restriction():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SANATAN", "discount_percent": 20, "allowed_ticket_type_ids": [adult.id]},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["allowed_ticket_type_ids"] == [adult.id]
        db.drop_all()


def test_admin_update_coupon_can_change_the_ticket_type_restriction():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult")
        child = _add_type(event.id, name="Child")
        coupon = _add_coupon(event.id, allowed_ticket_type_ids=str(adult.id))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/coupons/{coupon.id}",
                json={"allowed_ticket_type_ids": [adult.id, child.id]},
                headers=headers,
            )

        assert response.status_code == 200
        assert sorted(response.get_json()["allowed_ticket_type_ids"]) == sorted([adult.id, child.id])
        db.drop_all()


def test_admin_create_coupon_rejects_a_ticket_type_from_a_different_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        other_type = _add_type(other_event.id)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20, "allowed_ticket_type_ids": [other_type.id]},
                headers=headers,
            )

        assert response.status_code == 400
        assert "allowed_ticket_type_ids" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_coupon_rejects_a_non_list_ticket_type_restriction():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20, "allowed_ticket_type_ids": "1,2"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "allowed_ticket_type_ids" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_coupon_defaults_to_unlimited_redemptions():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20},
                headers=headers,
            )

        data = response.get_json()
        assert data["max_redemptions"] is None
        assert data["redemption_count"] == 0
        db.drop_all()


def test_admin_create_coupon_with_a_redemption_limit():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20, "max_redemptions": 50},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["max_redemptions"] == 50
        db.drop_all()


def test_admin_create_coupon_rejects_a_non_positive_redemption_limit():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "SAVE20", "discount_percent": 20, "max_redemptions": 0},
                headers=headers,
            )

        assert response.status_code == 400
        assert "max_redemptions" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_coupon_can_clear_the_redemption_limit():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        coupon = _add_coupon(event.id, max_redemptions=50)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/coupons/{coupon.id}", json={"max_redemptions": None}, headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["max_redemptions"] is None
        db.drop_all()


def test_admin_list_coupons_includes_the_paid_redemption_count():
    """redemption_count is a TICKET count, not an order count — a paid order with several
    tickets must count all of them, and a pending order (however many tickets) must count none."""
    app = _new_app()
    with app.app_context():
        from app.orders.models import Order, OrderItem
        from app.tickets.models import Ticket

        event = _add_event()
        adult = _add_type(event.id, name="Adult")
        coupon = _add_coupon(event.id, max_redemptions=50)

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
        paid_item = OrderItem(
            order_id=paid_order.id, ticket_type_id=adult.id, quantity=3, unit_price=15000, subtotal=0
        )
        db.session.add(paid_item)
        db.session.flush()
        db.session.add_all(
            [Ticket(order_item_id=paid_item.id, ticket_code=f"paid-{i}") for i in range(3)]
        )

        pending_order = Order(
            order_number="BCA-2026-000002",
            event_id=event.id,
            customer_name="Rahul Sen",
            customer_email="rahul@example.com",
            total_amount=12000,
            coupon_id=coupon.id,
            coupon_code=coupon.code,
            payment_status="pending",
        )
        db.session.add(pending_order)
        db.session.flush()
        pending_item = OrderItem(
            order_id=pending_order.id, ticket_type_id=adult.id, quantity=2, unit_price=15000, subtotal=30000
        )
        db.session.add(pending_item)
        db.session.commit()
        # No Ticket rows for the pending order — tickets are only issued once an order is paid,
        # matching this app's existing "tickets created only at paid" invariant elsewhere.
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/events/{event.id}/coupons", headers=headers
            )

        # 3 tickets from the paid order; the pending order's 2 requested units don't count yet.
        assert response.get_json()["items"][0]["redemption_count"] == 3
        db.drop_all()


def test_admin_create_coupon_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        event = _add_event()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/events/{event.id}/coupons",
                json={"code": "save20", "discount_percent": 20},
                headers=auth_header(token),
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "coupon_created"
        assert entry.target_type == "coupon"
        assert "SAVE20" in entry.description
        db.drop_all()


def test_admin_update_coupon_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        event = _add_event()
        coupon = _add_coupon(event.id)
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/coupons/{coupon.id}",
                json={"is_active": False},
                headers=auth_header(token),
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "coupon_updated"
        assert entry.target_type == "coupon"
        assert entry.target_id == coupon.id
        db.drop_all()
