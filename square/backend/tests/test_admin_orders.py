"""Tests for admin orders (33 tests), e.g. admin routes reject requests with no token; admin routes allow a cors preflight with no auth header; admin list orders."""
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
        "published": True,
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _checkout(client, event, items):
    payload = {
        "event_id": event.id,
        "items": items,
        "customer_name": "Priya Das",
        "customer_email": "priya@example.com",
        "customer_phone": "41234567",
    }
    return client.post("/api/orders", json=payload).get_json()


def _confirm_payment(client, order):
    """Mirrors the buyer's own "I've paid" report — transitions pending -> pending_
    verification, the only state mark-paid/reject accept."""
    return client.post(
        f"/api/orders/{order['order_number']}/confirm-payment",
        json={"email": order["customer_email"]},
    )


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/orders")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/orders", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_list_orders():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.get("/api/admin/orders", headers=headers)

        assert response.status_code == 200
        assert len(response.get_json()["items"]) == 1
        db.drop_all()


def test_admin_get_order_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/orders/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_mark_paid_generates_one_ticket_per_purchased_unit():
    from app.tickets.models import TicketType, Ticket

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = TicketType(event_id=event.id, name="Adult", price=15000)
        child = TicketType(event_id=event.id, name="Child", price=5000)
        db.session.add_all([adult, child])
        db.session.commit()
        client = app.test_client()
        created = _checkout(
            client,
            event,
            [
                {"ticket_type_id": adult.id, "quantity": 2},
                {"ticket_type_id": child.id, "quantity": 1},
            ],
        )
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["payment_status"] == "paid"
        assert data["order_status"] == "confirmed"
        assert Ticket.query.count() == 3
        all_tickets = [t for item in data["items"] for t in item["tickets"]]
        assert len(all_tickets) == 3
        assert all(t["qr_code_data_url"].startswith("data:image/png;base64,") for t in all_tickets)
        # Every ticket_code is unique.
        assert len({t["ticket_code"] for t in all_tickets}) == 3
        db.drop_all()


def test_mark_paid_auto_deactivates_a_coupon_at_its_redemption_limit():
    from app.coupons.models import Coupon
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        coupon = Coupon(
            event_id=event.id, code="SAVE20", discount_percent=20, max_redemptions=1
        )
        db.session.add(coupon)
        db.session.commit()
        client = app.test_client()
        created = client.post(
            "/api/orders",
            json={
                "event_id": event.id,
                "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}],
                "customer_name": "Priya Das",
                "customer_email": "priya@example.com",
                "customer_phone": "41234567",
                "coupon_code": "SAVE20",
            },
        ).get_json()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)

        assert response.status_code == 200
        assert db.session.get(Coupon, coupon.id).is_active is False
        db.drop_all()


def test_get_order_includes_check_in_details_once_a_ticket_is_scanned():
    from app.members.models import Member
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        # start_datetime=NOW, not the default 10-days-out — a scan is only accepted on the
        # event's own day (see app.checkin.admin_routes's pre_event/post_event date window).
        event = _add_event(start_datetime=NOW)
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        admin_user, token = make_user_and_token(role="admin", email="door@example.com")
        db.session.add(Member(user_id=admin_user.id, name="Door Volunteer"))
        db.session.commit()
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            mark_paid = client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)
            ticket_code = mark_paid.get_json()["items"][0]["tickets"][0]["ticket_code"]

            before_scan = client.get(f"/api/admin/orders/{created['id']}", headers=headers)
            unscanned = before_scan.get_json()["items"][0]["tickets"][0]
            assert unscanned["issued_at"] is not None
            assert before_scan.get_json()["created_at"] and before_scan.get_json()["updated_at"]
            assert all(p["created_at"] and p["updated_at"] for p in before_scan.get_json()["payments"])
            assert unscanned["checked_in_at"] is None
            assert unscanned["checked_in_by_email"] is None
            assert unscanned["checked_in_by_name"] is None

            client.post("/api/admin/checkin/scan", json={"ticket_code": ticket_code}, headers=headers)
            after_scan = client.get(f"/api/admin/orders/{created['id']}", headers=headers)

        scanned = after_scan.get_json()["items"][0]["tickets"][0]
        assert scanned["checked_in_at"] is not None
        assert scanned["checked_in_by_email"] == "door@example.com"
        assert scanned["checked_in_by_name"] == "Door Volunteer"
        db.drop_all()


def test_mark_paid_is_idempotent():
    from app.tickets.models import TicketType, Ticket

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 2}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)
            second_response = client.post(
                f"/api/admin/orders/{created['id']}/mark-paid", headers=headers
            )

        assert second_response.status_code == 200
        assert Ticket.query.count() == 2  # not 4 — the second call was a no-op
        db.drop_all()


def test_mark_paid_returns_404_for_unknown_order():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/orders/999/mark-paid", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_mark_paid_accepts_an_order_the_buyer_never_reported_paying():
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 2}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)

        assert response.status_code == 200
        assert response.get_json()["payment_status"] == "paid"
        assert Ticket.query.count() == 2
        db.drop_all()


def test_mark_paid_rejects_an_order_that_was_already_rejected():
    from app.orders.models import Order
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        db.session.get(Order, created["id"]).payment_status = "rejected"
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.post(f"/api/admin/orders/{created['id']}/mark-paid", headers=headers)

        assert response.status_code == 409
        assert Ticket.query.count() == 0
        db.drop_all()


def test_mark_paid_stamps_the_approving_admin_and_a_timestamp():
    from app.orders.models import Order
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(
                f"/api/admin/orders/{created['id']}/mark-paid", headers=auth_header(token)
            )

        data = response.get_json()
        assert data["approved_by_name"] is None
        assert data["approved_by_email"] == "admin@example.com"
        assert data["approved_at"] is not None
        order = db.session.get(Order, created["id"])
        assert order.approved_by_user_id == admin_user.id
        assert order.approved_at is not None
        db.drop_all()


def test_mark_paid_prefers_the_approving_admin_s_member_name_over_their_email():
    from app.members.models import Member
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")
        db.session.add(Member(user_id=admin_user.id, name="Priya Das", email="admin@example.com"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(
                f"/api/admin/orders/{created['id']}/mark-paid", headers=auth_header(token)
            )

        assert response.get_json()["approved_by_name"] == "Priya Das"
        db.drop_all()


def test_reject_requires_a_reason():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(
                f"/api/admin/orders/{created['id']}/reject", headers=headers, json={"reason": "  "}
            )

        assert response.status_code == 400
        assert "reason" in response.get_json()["errors"]
        db.drop_all()


def test_reject_a_pending_order_that_was_never_confirmed():
    """An admin can reject a plain "pending" order directly — e.g. a stale/abandoned cash
    order — without the buyer ever having claimed to have paid (pending_verification)."""
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        assert created["payment_status"] == "pending"
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.post(
                f"/api/admin/orders/{created['id']}/reject",
                headers=headers,
                json={"reason": "Never followed up on payment"},
            )

        assert response.status_code == 200
        assert response.get_json()["payment_status"] == "rejected"
        db.drop_all()


def test_reject_returns_409_for_an_order_already_paid():
    from app.orders.models import Order
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        db.session.get(Order, created["id"]).payment_status = "paid"
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.post(
                f"/api/admin/orders/{created['id']}/reject",
                headers=headers,
                json={"reason": "Screenshot doesn't match order total"},
            )

        assert response.status_code == 409
        db.drop_all()


def test_reject_stamps_the_rejecting_admin_reason_and_timestamp():
    from app.orders.models import Order
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            response = client.post(
                f"/api/admin/orders/{created['id']}/reject",
                headers=auth_header(token),
                json={"reason": "Screenshot doesn't match order total"},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["payment_status"] == "rejected"
        assert data["order_status"] == "cancelled"
        assert data["rejected_by_name"] is None
        assert data["rejected_by_email"] == "admin@example.com"
        assert data["rejected_at"] is not None
        assert data["rejection_reason"] == "Screenshot doesn't match order total"
        order = db.session.get(Order, created["id"])
        assert order.rejected_by_user_id == admin_user.id
        assert Ticket.query.count() == 0  # a rejected order never gets tickets
        db.drop_all()


def test_reject_is_idempotent():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, created)
            client.post(
                f"/api/admin/orders/{created['id']}/reject",
                headers=headers,
                json={"reason": "First reason"},
            )
            second_response = client.post(
                f"/api/admin/orders/{created['id']}/reject",
                headers=headers,
                json={"reason": "Second reason"},
            )

        assert second_response.status_code == 200
        assert second_response.get_json()["rejection_reason"] == "First reason"
        db.drop_all()


def test_reject_returns_404_for_unknown_order():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/orders/999/reject", headers=headers, json={"reason": "Nope"}
            )
        assert response.status_code == 404
        db.drop_all()


def test_reject_logs_an_audit_entry():
    from app.audit.models import AuditLog
    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000, payment_status="pending_verification")
        db.session.add(order)
        db.session.commit()
        db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                                 unit_price=15000, subtotal=15000))
        db.session.commit()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/orders/{order.id}/reject",
                headers=auth_header(token),
                json={"reason": "Payment not received"},
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "order_rejected"
        assert entry.target_type == "order"
        assert entry.target_id == order.id
        assert "Payment not received" in entry.description
        db.drop_all()


def _mark_paid(client, order, headers):
    """Checkout -> admin mark-paid, the only way a real Ticket row exists outside a $0 coupon
    order — mirrors mark-paid's own tests."""
    return client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)


def test_cancel_a_paid_order_voids_valid_tickets_and_stamps_reason():
    from app.orders.models import Order
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 2}])
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            response = client.post(
                f"/api/admin/orders/{created['id']}/cancel",
                headers=headers,
                json={"reason": "Event postponed"},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["payment_status"] == "cancelled"
        assert data["order_status"] == "cancelled"
        assert data["cancelled_by_email"] == "admin@example.com"
        assert data["cancellation_reason"] == "Event postponed"
        order = db.session.get(Order, created["id"])
        assert order.cancelled_by_user_id == admin_user.id
        assert all(t.status == "void" for t in Ticket.query.all())
        db.drop_all()


def test_cancel_is_refused_once_a_ticket_is_checked_in():
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 2}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            tickets = Ticket.query.order_by(Ticket.id).all()
            tickets[0].status = "used"
            db.session.commit()

            response = client.post(
                f"/api/admin/orders/{created['id']}/cancel",
                headers=headers,
                json={"reason": "Duplicate order"},
            )

        assert response.status_code == 409
        tickets = Ticket.query.order_by(Ticket.id).all()
        assert tickets[0].status == "used"
        assert tickets[1].status == "valid"
        db.drop_all()


def test_cancel_returns_409_for_a_non_paid_order():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.post(
                f"/api/admin/orders/{created['id']}/cancel", headers=headers, json={"reason": "x"}
            )

        assert response.status_code == 409
        db.drop_all()


def test_cancel_requires_a_reason():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            response = client.post(
                f"/api/admin/orders/{created['id']}/cancel", headers=headers, json={"reason": "  "}
            )

        assert response.status_code == 400
        assert "reason" in response.get_json()["errors"]
        db.drop_all()


def test_cancel_is_idempotent():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            client.post(
                f"/api/admin/orders/{created['id']}/cancel", headers=headers,
                json={"reason": "First reason"},
            )
            second_response = client.post(
                f"/api/admin/orders/{created['id']}/cancel", headers=headers,
                json={"reason": "Second reason"},
            )

        assert second_response.status_code == 200
        assert second_response.get_json()["cancellation_reason"] == "First reason"
        db.drop_all()


def test_cancel_frees_up_the_coupons_redemption_count():
    from app.coupons.models import Coupon, redemption_count_for_coupon
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        coupon = Coupon(event_id=event.id, code="SAVE20", discount_percent=20, max_redemptions=5)
        db.session.add(coupon)
        db.session.commit()
        client = app.test_client()
        created = client.post(
            "/api/orders",
            json={
                "event_id": event.id,
                "items": [{"ticket_type_id": ticket_type.id, "quantity": 2}],
                "customer_name": "Priya Das",
                "customer_email": "priya@example.com",
                "customer_phone": "41234567",
                "coupon_code": "SAVE20",
            },
        ).get_json()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            assert redemption_count_for_coupon(coupon.id) == 2

            client.post(
                f"/api/admin/orders/{created['id']}/cancel", headers=headers,
                json={"reason": "Refund requested"},
            )

        assert redemption_count_for_coupon(coupon.id) == 0
        db.drop_all()


def test_cancel_logs_an_audit_entry():
    from app.audit.models import AuditLog
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        created = _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 1}])
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _mark_paid(client, created, headers)
            client.post(
                f"/api/admin/orders/{created['id']}/cancel",
                headers=headers,
                json={"reason": "Event postponed"},
            )

        entry = AuditLog.query.filter_by(action="order_cancelled").one()
        assert entry.actor_user_id == admin_user.id
        assert entry.target_type == "order"
        assert entry.target_id == created["id"]
        assert "Event postponed" in entry.description
        db.drop_all()


def test_list_orders_payment_status_filter_accepts_several_comma_separated_values():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        for number, status in [
            ("BCA-2026-000001", "pending"),
            ("BCA-2026-000002", "pending_verification"),
            ("BCA-2026-000003", "paid"),
        ]:
            db.session.add(Order(order_number=number, event_id=event.id, customer_name="Priya Das",
                                 customer_email="priya@example.com", total_amount=15000,
                                 payment_status=status))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/orders?payment_status=pending,pending_verification", headers=headers
            )

        data = response.get_json()
        assert data["total"] == 2
        assert {o["payment_status"] for o in data["items"]} == {"pending", "pending_verification"}
        db.drop_all()


def test_export_orders_returns_an_xlsx_file_with_one_row_per_ticket_line():
    from io import BytesIO

    from openpyxl import load_workbook

    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        client = app.test_client()
        _checkout(client, event, [{"ticket_type_id": ticket_type.id, "quantity": 2}])
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = client.get("/api/admin/orders/export", headers=headers)

        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type

        workbook = load_workbook(BytesIO(response.data))
        rows = list(workbook.active.iter_rows(values_only=True))
        assert rows[0][0] == "Order number"
        assert rows[1][3] == "Durga Puja 2026"  # event title column
        assert rows[1][4] == "Adult"
        assert rows[1][5] == 2
        db.drop_all()


def test_mark_paid_logs_an_audit_entry():
    from app.audit.models import AuditLog
    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000, payment_status="pending_verification")
        db.session.add(order)
        db.session.commit()
        db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                                 unit_price=15000, subtotal=15000))
        db.session.commit()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/orders/{order.id}/mark-paid", headers=auth_header(token)
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "order_marked_paid"
        assert entry.target_type == "order"
        assert entry.target_id == order.id
        assert "BCA-2026-000001" in entry.description
        db.drop_all()


def test_marking_an_already_paid_order_paid_again_does_not_log_twice():
    from app.audit.models import AuditLog
    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000, payment_status="pending_verification")
        db.session.add(order)
        db.session.commit()
        db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                                 unit_price=15000, subtotal=15000))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post(f"/api/admin/orders/{order.id}/mark-paid", headers=headers)
            client.post(f"/api/admin/orders/{order.id}/mark-paid", headers=headers)

        assert AuditLog.query.count() == 1
        db.drop_all()


def test_list_orders_q_searches_order_number_name_email_and_phone():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        for number, name, email, phone in [
            ("BCA-2026-000101", "Priya Das", "priya@example.com", "91234567"),
            ("BCA-2026-000102", "Arjun Sen", "arjun@example.org", "98765432"),
        ]:
            db.session.add(Order(order_number=number, event_id=event.id, customer_name=name,
                                 customer_email=email, customer_phone=phone, total_amount=15000,
                                 payment_status="paid"))
        db.session.commit()
        headers = _admin_headers()

        def numbers(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/orders?q={query}", headers=headers)
            assert response.status_code == 200
            return {o["order_number"] for o in response.get_json()["items"]}

        assert numbers("000102") == {"BCA-2026-000102"}
        assert numbers("priya") == {"BCA-2026-000101"}
        assert numbers("example.org") == {"BCA-2026-000102"}
        assert numbers("9876") == {"BCA-2026-000102"}
        assert numbers("nobody") == set()
        assert numbers("") == {"BCA-2026-000101", "BCA-2026-000102"}
        db.drop_all()


def test_export_orders_uses_the_same_filters_as_the_list():
    from io import BytesIO

    from openpyxl import load_workbook

    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        for number, name, status in (("BCA-2026-000001", "Priya Das", "paid"), ("BCA-2026-000002", "Rohan Sen", "pending")):
            order = Order(order_number=number, event_id=event.id, customer_name=name,
                          customer_email=f"{name.split()[0].lower()}@example.com", total_amount=15000, payment_status=status)
            db.session.add(order)
            db.session.commit()
            db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1, unit_price=15000, subtotal=15000))
        db.session.commit()
        headers = _admin_headers()

        def exported(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/orders/export{query}", headers=headers)
            assert response.status_code == 200
            return [r[0] for r in list(load_workbook(BytesIO(response.data)).active.iter_rows(values_only=True))[1:]]

        assert exported("") == ["BCA-2026-000002", "BCA-2026-000001"]
        assert exported("?payment_status=paid") == ["BCA-2026-000001"]
        assert exported("?q=rohan") == ["BCA-2026-000002"]
        assert exported("?payment_status=paid&q=rohan") == []
        db.drop_all()
