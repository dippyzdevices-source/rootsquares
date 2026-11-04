"""Tests for membership drive (15 tests), e.g. signup requires a token; signup rejects a member role; signup allows a volunteer role."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod, MembershipType
from app.payments.models import Payment, PaymentAllocation
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


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


def _add_type(**overrides):
    defaults = {"name": "Individual", "price": 300, "billing_frequency": "yearly"}
    defaults.update(overrides)
    membership_type = MembershipType(**defaults)
    db.session.add(membership_type)
    db.session.commit()
    return membership_type


def _valid_payload(**overrides):
    payload = {
        "name": "Priya Das",
        "email": "priya@example.com",
        "phone": "41234567",
        "membership_type": "Individual",
    }
    payload.update(overrides)
    return payload


def test_signup_requires_a_token():
    app = _new_app()
    with app.app_context():
        _add_type()
        response = app.test_client().post("/api/admin/membership-drive/signup", json={})
        assert response.status_code == 401
        db.drop_all()


def test_signup_rejects_a_member_role():
    app = _new_app()
    with app.app_context():
        _add_type()
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json=_valid_payload(), headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_signup_allows_a_volunteer_role():
    app = _new_app()
    with app.app_context():
        _add_type()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json=_valid_payload(), headers=_volunteer_headers()
            )
        assert response.status_code == 201
        db.drop_all()


def test_signup_validates_required_fields_and_type():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json={}, headers=_admin_headers()
            )
        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert set(errors) == {"name", "email", "membership_type"}
        db.drop_all()


def test_signup_rejects_an_invalid_email_and_phone():
    app = _new_app()
    with app.app_context():
        _add_type()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(email="not-an-email", phone="123"),
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert "email" in errors
        assert "phone" in errors
        db.drop_all()


def test_signup_rejects_an_inactive_membership_type():
    app = _new_app()
    with app.app_context():
        _add_type(name="Retired", is_active=False)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(membership_type="Retired"),
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "membership_type" in response.get_json()["errors"]
        db.drop_all()


def test_signup_creates_an_active_membership_and_pays_the_current_period_for_a_yearly_type():
    app = _new_app()
    with app.app_context():
        _add_type(name="Individual", price=300, billing_frequency="yearly")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json=_valid_payload(), headers=_admin_headers()
            )

        assert response.status_code == 201
        body = response.get_json()

        member = Member.query.filter_by(email="priya@example.com").one()
        assert member.name == "Priya Das"
        assert member.user_id is None

        membership = Membership.query.filter_by(member_id=member.id).one()
        assert membership.status == "active"
        assert membership.start_date == date.today()

        periods = MembershipPeriod.query.filter_by(membership_id=membership.id).all()
        assert len(periods) == 1
        assert periods[0].status == "paid"

        payment = Payment.query.one()
        assert payment.payment_type == "membership"
        assert payment.provider == "vipps_qr"
        assert payment.status == "paid"
        assert payment.amount == 30000  # 300 NOK -> øre
        assert PaymentAllocation.query.filter_by(payment_id=payment.id).count() == 1
        assert body["payment"]["amount"] == 30000

        assert AuditLog.query.filter_by(action="membership_drive_signup").count() == 1
        db.drop_all()


def test_signup_only_pays_the_current_months_period_for_a_monthly_type():
    app = _new_app()
    with app.app_context():
        _add_type(name="Monthly Plan", price=50, billing_frequency="monthly")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(membership_type="Monthly Plan"),
                headers=_admin_headers(),
            )

        assert response.status_code == 201
        member = Member.query.filter_by(email="priya@example.com").one()
        membership = Membership.query.filter_by(member_id=member.id).one()

        periods = MembershipPeriod.query.filter_by(membership_id=membership.id).order_by(
            MembershipPeriod.period_start
        ).all()
        assert len(periods) == 12
        paid = [p for p in periods if p.status == "paid"]
        unpaid = [p for p in periods if p.status == "unpaid"]
        assert len(paid) == 1
        assert len(unpaid) == 11

        today = date.today()
        assert paid[0].period_start <= today <= paid[0].period_end

        payment = Payment.query.one()
        assert payment.amount == 5000  # one month, 50 NOK -> øre
        db.drop_all()


def test_signup_activates_with_no_payment_for_a_contact_for_price_type():
    app = _new_app()
    with app.app_context():
        _add_type(name="Lifetime", price=0, contact_for_price=True)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(membership_type="Lifetime"),
                headers=_admin_headers(),
            )

        assert response.status_code == 201
        assert response.get_json()["payment"] is None

        member = Member.query.filter_by(email="priya@example.com").one()
        membership = Membership.query.filter_by(member_id=member.id).one()
        assert membership.status == "active"
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 0
        assert Payment.query.count() == 0
        db.drop_all()


def test_signup_reuses_an_existing_unlinked_member_by_email_instead_of_duplicating():
    app = _new_app()
    with app.app_context():
        _add_type()
        existing = Member(name="Priya Das (imported)", email="priya@example.com", phone="00000000")
        db.session.add(existing)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json=_valid_payload(), headers=_admin_headers()
            )

        assert response.status_code == 201
        assert Member.query.count() == 1
        assert response.get_json()["member"]["id"] == existing.id
        assert Membership.query.filter_by(member_id=existing.id).count() == 1
        db.drop_all()


def test_signup_reuses_an_existing_linked_member_matched_by_their_users_current_email():
    app = _new_app()
    with app.app_context():
        _add_type()
        user, _ = make_user_and_token(email="priya@example.com")
        existing = Member(user_id=user.id, name="Priya Das", email="stale@example.com")
        db.session.add(existing)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup", json=_valid_payload(), headers=_admin_headers()
            )

        assert response.status_code == 201
        assert Member.query.count() == 1
        assert response.get_json()["member"]["id"] == existing.id
        db.drop_all()


def test_pay_later_saves_a_pending_request_with_periods_and_no_payment():
    app = _new_app()
    with app.app_context():
        _add_type()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(payment_method="pay_later"),
                headers=_admin_headers(),
            )
        assert response.status_code == 201
        body = response.get_json()
        assert body["membership"]["status"] == "pending"
        assert body["payment"] is None
        membership = db.session.get(Membership, body["membership"]["id"])
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 1
        assert Payment.query.count() == 0
        db.drop_all()


def test_pay_later_is_ignored_for_a_type_with_no_price():
    app = _new_app()
    with app.app_context():
        _add_type(name="Lifetime", price=0, contact_for_price=True)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(membership_type="Lifetime", payment_method="pay_later"),
                headers=_admin_headers(),
            )
        assert response.status_code == 201
        assert response.get_json()["membership"]["status"] == "active"
        db.drop_all()


def test_child_can_pay_later_and_the_parent_pays_for_them_from_their_own_account():
    app = _new_app()
    with app.app_context():
        _add_type()
        _add_type(name="child", price=100)
        parent = Member(name="Anil Das", email="anil@example.com", phone="41234567")
        db.session.add(parent)
        db.session.commit()
        db.session.add(Membership(member_id=parent.id, membership_type="Individual", status="active", start_date=date.today()))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.post(
                "/api/admin/membership-drive/signup",
                json={"name": "Mini Das", "parent_email": "anil@example.com", "membership_type": "child", "payment_method": "pay_later"},
                headers=_admin_headers(),
            )
            assert response.status_code == 201
            assert response.get_json()["membership"]["status"] == "pending"
            assert response.get_json()["payment"] is None

            _, token = make_user_and_token(role="member", email="anil@example.com")
            headers = auth_header(token)
            awaiting = client.get("/api/memberships/me/children-awaiting", headers=headers).get_json()["items"]
            assert [i["name"] for i in awaiting] == ["Mini Das"]
            period_id = awaiting[0]["period"]["id"]

            paid = client.post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [period_id], "provider": "vipps_qr"},
                headers=headers,
            )
            assert paid.status_code == 200
            # someone else's child can't be paid for
            _, other = make_user_and_token(role="member", email="other@example.com")
            denied = client.post(
                "/api/memberships/me/payments",
                json={"membership_period_ids": [period_id], "provider": "vipps_qr"},
                headers=auth_header(other),
            )
            assert denied.status_code in (400, 404)
        db.drop_all()


def test_phone_is_optional_but_must_be_valid_when_given():
    app = _new_app()
    with app.app_context():
        _add_type()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            payload = _valid_payload()
            del payload["phone"]
            ok = client.post("/api/admin/membership-drive/signup", json=payload, headers=_admin_headers())
            assert ok.status_code == 201
            assert Member.query.filter_by(email="priya@example.com").one().phone is None

            bad = client.post(
                "/api/admin/membership-drive/signup",
                json=_valid_payload(email="other@example.com", phone="123"),
                headers=_admin_headers(),
            )
            assert bad.status_code == 400 and "phone" in bad.get_json()["errors"]
        db.drop_all()
