"""Tests for order customer member (4 tests), e.g. buyer with an active membership is a member with type photo and link; buyer whose membership ended is a former member; buyer nobody knows or without any membership is a guest."""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_cash_payments import _new_app, _post_order
from tests.test_orders_checkout import _add_event, _add_type


def _order_detail(app, email_member=None, memberships=()):
    """Places a cash order as priya@example.com (the checkout helper's customer) and returns the admin view."""
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType
    from app.orders.models import Order

    event = _add_event(ticket_payment_methods="qr,cash")
    tt = _add_type(event.id)
    _post_order(app, event, tt, "cash")
    if email_member:
        db.session.add(MembershipType(name="individual", price=100, billing_frequency="yearly"))
        member = Member(name="Priya Das", email=email_member, photo_url="https://img.test/priya.webp")
        db.session.add(member)
        db.session.commit()
        for status in memberships:
            db.session.add(Membership(member_id=member.id, membership_type="individual", status=status, start_date=date(2026, 1, 1)))
        db.session.commit()
    order = Order.query.one()
    _, token = make_user_and_token(role="admin")
    return app.test_client().get(f"/api/admin/orders/{order.id}", headers=auth_header(token)).get_json()


def test_buyer_with_an_active_membership_is_a_member_with_type_photo_and_link():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        info = _order_detail(app, "priya@example.com", ["expired", "active"])["customer_member"]
        assert info["status"] == "member" and info["membership_type"] == "individual"
        assert info["photo_url"] == "https://img.test/priya.webp" and info["member_id"]
        db.drop_all()


def test_buyer_whose_membership_ended_is_a_former_member():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        info = _order_detail(app, "priya@example.com", ["expired"])["customer_member"]
        assert info["status"] == "former" and info["membership_type"] == "individual"
        db.drop_all()


def test_buyer_nobody_knows_or_without_any_membership_is_a_guest():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        assert _order_detail(app)["customer_member"] == {"status": "guest", "member_id": None, "membership_type": None, "photo_url": None}
        db.drop_all()
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        assert _order_detail(app, "priya@example.com", [])["customer_member"]["status"] == "guest"
        db.drop_all()


def test_order_reports_its_coupon_percentage_when_the_coupon_still_exists():
    from app.coupons.models import Coupon
    from app.orders.models import Order

    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _order_detail(app)
        order = Order.query.one()
        assert app.test_client().get(f"/api/admin/orders/{order.id}", headers=auth_header(make_user_and_token(role="admin")[1])).get_json()["coupon_percent"] is None

        coupon = Coupon(event_id=order.event_id, code="MEMBER", discount_percent=100)
        db.session.add(coupon)
        db.session.commit()
        order.coupon_id, order.coupon_code = coupon.id, "MEMBER"
        db.session.commit()
        body = app.test_client().get(f"/api/admin/orders/{order.id}", headers=auth_header(make_user_and_token(role="admin")[1])).get_json()
        assert body["coupon_percent"] == 100 and body["coupon_code"] == "MEMBER"
        db.drop_all()
