"""Tests for memberships routes (12 tests), e.g. list membership types is public and returns only active ones; list membership types hides the real price when contact for price is s; list my memberships requires auth."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _seed_membership_types():
    db.session.add_all(
        [MembershipType(name="individual", price=0), MembershipType(name="family", price=0)]
    )
    db.session.commit()


def test_list_membership_types_is_public_and_returns_only_active_ones():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                MembershipType(name="individual", price=500, sort_order=1),
                MembershipType(name="retired", price=0, is_active=False, sort_order=0),
            ]
        )
        db.session.commit()

        response = app.test_client().get("/api/memberships/types")

        assert response.status_code == 200
        assert response.get_json() == {
            "items": [
                {
                    "name": "individual",
                    "price": 500,
                    "billing_frequency": "yearly",
                    "contact_for_price": False,
                    "description": None,
                }
            ]
        }
        db.drop_all()


def test_list_membership_types_hides_the_real_price_when_contact_for_price_is_set():
    app = _new_app()
    with app.app_context():
        db.session.add(
            MembershipType(name="lifetime", price=5000, contact_for_price=True, billing_frequency="yearly")
        )
        db.session.commit()

        response = app.test_client().get("/api/memberships/types")

        item = response.get_json()["items"][0]
        assert item["contact_for_price"] is True
        assert item["price"] is None
        db.drop_all()


def test_list_my_memberships_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/memberships/me")
        assert response.status_code == 401
        db.drop_all()


def test_list_my_memberships_returns_empty_when_no_member_profile_exists():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/memberships/me", headers=auth_header(token))
        assert response.status_code == 200
        assert response.get_json() == {"items": []}
        db.drop_all()


def test_list_my_memberships_returns_only_the_current_users_memberships_newest_first():
    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(email="a@b.com")
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="expired",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            )
        )
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="active",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        # An unrelated member's membership must never show up here.
        other_user = type(user)(auth_user_id="other-sub", auth_provider="supabase", email="other@example.com")
        db.session.add(other_user)
        db.session.commit()
        other_member = Member(user_id=other_user.id, name="Other Person")
        db.session.add(other_member)
        db.session.commit()
        db.session.add(
            Membership(
                member_id=other_member.id, membership_type="family", start_date=date(2026, 1, 1)
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/memberships/me", headers=auth_header(token))

        items = response.get_json()["items"]
        assert len(items) == 2
        assert items[0]["status"] == "active"
        assert items[1]["status"] == "expired"

        db.drop_all()


def test_request_renewal_requires_auth():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post(
            "/api/memberships/me", json={"membership_type": "individual"}
        )
        assert response.status_code == 401
        db.drop_all()


def test_request_renewal_auto_links_an_imported_member_by_email():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        db.session.add(Member(name="Priya Das", email="priya@example.com"))
        db.session.commit()

        user, token = make_user_and_token(email="priya@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "individual"},
                headers=auth_header(token),
            )

        assert response.status_code == 201
        member = Member.query.filter_by(email="priya@example.com").one()
        assert member.user_id == user.id
        db.drop_all()


def test_request_renewal_requires_a_member_profile_first():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "individual"},
                headers=auth_header(token),
            )
        assert response.status_code == 400
        db.drop_all()


def test_request_renewal_creates_a_pending_membership():
    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        user, token = make_user_and_token(email="a@b.com")
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "family"},
                headers=auth_header(token),
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"
        assert data["membership_type"] == "family"
        assert Membership.query.filter_by(member_id=member.id).count() == 1
        db.drop_all()


def test_request_renewal_rejects_an_invalid_membership_type():
    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(email="a@b.com")
        db.session.add(Member(user_id=user.id, name="Priya Das"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "not-a-real-type"},
                headers=auth_header(token),
            )

        assert response.status_code == 400
        db.drop_all()


def test_request_renewal_rejects_a_new_request_when_already_active():
    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        user, token = make_user_and_token(email="a@b.com")
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="active",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "individual"},
                headers=auth_header(token),
            )

        assert response.status_code == 409
        db.drop_all()


def test_request_renewal_rejects_a_new_request_while_one_is_already_being_paid():
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment, PaymentAllocation

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        user, token = make_user_and_token(email="a@b.com")
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()
        membership = Membership(
            member_id=member.id,
            membership_type="individual",
            status="pending",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()
        # A reported (pending) payment locks the request: it can no longer be swapped.
        period = MembershipPeriod(
            membership_id=membership.id, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            label="2026", amount=0,
        )
        db.session.add(period)
        payment = Payment(payment_type="membership", provider="vipps", amount=0, status="pending")
        db.session.add(payment)
        db.session.commit()
        db.session.add(PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=0))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/memberships/me",
                json={"membership_type": "individual"},
                headers=auth_header(token),
            )

        assert response.status_code == 409
        assert Membership.query.filter_by(member_id=member.id).count() == 1
        db.drop_all()
