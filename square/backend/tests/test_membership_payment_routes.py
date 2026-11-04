"""Tests for membership payment routes (12 tests), e.g. get periods requires auth; start payment requires auth; get periods returns only the current members periods."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _make_member_with_active_membership(billing_frequency="monthly", price=200):
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType
    from app.memberships.service import generate_periods_for_membership

    user, token = make_user_and_token(email="priya@example.com")
    type_name = f"type-{billing_frequency}"
    if not db.session.get(MembershipType, type_name):
        db.session.add(MembershipType(name=type_name, price=price, billing_frequency=billing_frequency))
    member = Member(user_id=user.id, name="Priya Das")
    db.session.add(member)
    db.session.commit()
    membership = Membership(
        member_id=member.id, membership_type=type_name, status="active",
        start_date=date(2027, 1, 1),
    )
    db.session.add(membership)
    db.session.commit()
    generate_periods_for_membership(membership)
    return member, membership, token


def test_get_periods_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/memberships/me/periods")
        assert response.status_code == 401
        db.drop_all()


def test_start_payment_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post(
            "/api/memberships/me/payments",
            json={"membership_period_ids": [1], "provider": "vipps"},
        )
        assert response.status_code == 401
        db.drop_all()


def test_get_periods_returns_only_the_current_members_periods():
    app = _new_app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/memberships/me/periods", headers=auth_header(token)
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["membership"]["id"] == membership.id
        assert len(data["items"]) == 12
        assert data["items"][0]["status"] == "unpaid"
        db.drop_all()


def test_start_payment_rejects_a_period_that_is_not_the_callers():
    app = _new_app()
    with app.app_context():
        _, membership, _ = _make_member_with_active_membership()
        from app.memberships.models import MembershipPeriod

        other_period = MembershipPeriod.query.filter_by(membership_id=membership.id).first()

        _, _, other_token = _make_member_with_active_membership()  # a second, unrelated member
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [other_period.id], "provider": "vipps"},
                headers=auth_header(other_token),
            )

        assert response.status_code == 400
        db.drop_all()


def test_start_payment_rejects_an_already_paid_period():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod

        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id).first()
        period.status = "paid"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [period.id], "provider": "vipps"},
                headers=auth_header(token),
            )

        assert response.status_code == 400
        db.drop_all()


def test_start_payment_rejects_provider_manual():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod

        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id).first()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [period.id], "provider": "manual"},
                headers=auth_header(token),
            )

        assert response.status_code == 400
        db.drop_all()


def test_start_payment_with_stripe_is_refused_while_stripe_is_not_connected():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod

        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id).first()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [period.id], "provider": "stripe"},
                headers=auth_header(token),
            )
        assert response.status_code == 503
        db.drop_all()


def test_start_payment_rejects_a_period_already_awaiting_confirmation():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod

        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id).first()
        body = {"membership_period_ids": [period.id], "provider": "vipps"}
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            assert client.post("/api/memberships/me/payments", json=body, headers=auth_header(token)).status_code == 200
            assert client.post("/api/memberships/me/payments", json=body, headers=auth_header(token)).status_code == 400
            items = client.get("/api/memberships/me/periods", headers=auth_header(token)).get_json()["items"]
        assert next(i for i in items if i["id"] == period.id)["payment_pending"] is True
        db.drop_all()


def test_start_payment_ignores_a_client_submitted_total_and_computes_its_own():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod
        from app.payments.models import Payment

        _, membership, token = _make_member_with_active_membership(price=200)
        periods = MembershipPeriod.query.filter_by(membership_id=membership.id).order_by(
            MembershipPeriod.period_start
        ).limit(2).all()
        period_ids = [p.id for p in periods]

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                # a client-submitted "amount" the endpoint must never accept as-is
                json={"membership_period_ids": period_ids, "provider": "vipps", "amount": 1},
                headers=auth_header(token),
            )

        assert response.status_code == 200
        payment_id = response.get_json()["payment"]["id"]
        payment = db.session.get(Payment, payment_id)
        assert payment.amount == 40000  # 2 x 20000, computed server-side, never 1
        db.drop_all()


def test_start_payment_happy_path_creates_a_pending_payment_and_allocations():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod
        from app.payments.models import Payment, PaymentAllocation

        _, membership, token = _make_member_with_active_membership(price=200)
        periods = MembershipPeriod.query.filter_by(membership_id=membership.id).order_by(
            MembershipPeriod.period_start
        ).limit(3).all()
        period_ids = [p.id for p in periods]

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": period_ids, "provider": "vipps"},
                headers=auth_header(token),
            )

        assert response.status_code == 200
        payment = Payment.query.one()
        assert payment.status == "pending"
        assert payment.amount == 60000
        assert payment.payment_reference is not None
        assert PaymentAllocation.query.filter_by(payment_id=payment.id).count() == 3
        for period_id in period_ids:
            assert db.session.get(MembershipPeriod, period_id).status == "unpaid"
        db.drop_all()


def test_get_my_membership_payments_lists_only_my_own_payments_with_allocations():
    app = _new_app()
    with app.app_context():
        from app.memberships.models import MembershipPeriod

        _, membership, token = _make_member_with_active_membership(price=200)
        periods = MembershipPeriod.query.filter_by(membership_id=membership.id).order_by(
            MembershipPeriod.period_start
        ).limit(2).all()
        period_ids = [p.id for p in periods]

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": period_ids, "provider": "vipps"},
                headers=auth_header(token),
            )
            response = client.get("/api/memberships/me/payments", headers=auth_header(token))

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["amount"] == 40000
        assert len(data["items"][0]["allocations"]) == 2
        assert data["items"][0]["allocations"][0]["label"] in {p.label for p in periods}
        db.drop_all()


def test_get_my_membership_payments_is_empty_for_a_member_with_no_payments():
    app = _new_app()
    with app.app_context():
        _, _, token = _make_member_with_active_membership()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/memberships/me/payments", headers=auth_header(token)
            )

        assert response.status_code == 200
        assert response.get_json()["items"] == []
        db.drop_all()
