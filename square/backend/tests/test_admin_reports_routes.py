"""Tests for admin reports routes (7 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from datetime import date, datetime, timezone
from unittest.mock import patch

from app import create_app
from app.events.models import Event
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipType
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


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/reports/summary")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/reports/summary", headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/reports/summary", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_summary_is_all_zero_with_no_data():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/reports/summary", headers=_admin_headers()
            )

        assert response.status_code == 200
        assert response.get_json() == {
            "revenue_total": 0,
            "tickets_total": 0,
            "memberships_by_status": {},
            "memberships_by_type": {},
            "memberships_active_by_type": {},
            "orders_by_status": {},
        }
        db.drop_all()


def test_summary_sums_revenue_from_paid_orders_only():
    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW)
        db.session.add(event)
        db.session.commit()
        db.session.add(Order(order_number="BCA-2026-000001", event_id=event.id,
                             customer_name="Priya Das", customer_email="priya@example.com",
                             total_amount=15000, payment_status="paid"))
        db.session.add(Order(order_number="BCA-2026-000002", event_id=event.id,
                             customer_name="Rohan Sen", customer_email="rohan@example.com",
                             total_amount=30000, payment_status="pending"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/reports/summary", headers=_admin_headers()
            )

        data = response.get_json()
        assert data["revenue_total"] == 15000
        assert data["orders_by_status"] == {"paid": 1, "pending": 1}
        db.drop_all()


def test_summary_counts_tickets_total_and_checked_in():
    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW)
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=30000, payment_status="paid")
        db.session.add(order)
        db.session.commit()
        item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=2,
                         unit_price=15000, subtotal=30000)
        db.session.add(item)
        db.session.commit()
        db.session.add(Ticket(order_item_id=item.id, ticket_code="code1", status="used"))
        db.session.add(Ticket(order_item_id=item.id, ticket_code="code2", status="valid"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/reports/summary", headers=_admin_headers()
            )

        data = response.get_json()
        assert data["tickets_total"] == 2
        db.drop_all()


def test_summary_groups_memberships_by_status_and_type():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                MembershipType(name="individual", price=500),
                MembershipType(name="family", price=800),
            ]
        )
        member = Member(name="Priya Das", email="priya@example.com")
        db.session.add(member)
        db.session.commit()
        db.session.add(Membership(member_id=member.id, membership_type="individual",
                                  status="active", start_date=date(2026, 1, 1)))
        db.session.add(Membership(member_id=member.id, membership_type="family",
                                  status="pending", start_date=date(2026, 1, 1)))
        db.session.add(Membership(member_id=member.id, membership_type="individual",
                                  status="active", start_date=date(2025, 1, 1)))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/reports/summary", headers=_admin_headers()
            )

        data = response.get_json()
        assert data["memberships_by_status"] == {"active": 2, "pending": 1}
        assert data["memberships_by_type"] == {"individual": 2, "family": 1}
        assert data["memberships_active_by_type"] == {"individual": 2}
        db.drop_all()
