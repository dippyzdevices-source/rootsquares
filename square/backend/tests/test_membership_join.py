"""Tests for membership join (10 tests), e.g. options always offer pay later and follow the switches; pay later creates a pending request with periods and no payment; vipps qr creates a pending payment for the current period only."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod, MembershipType
from app.payments.models import Payment, PaymentAllocation
from app.settings.models import get_site_settings


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_type(name="adult", price=300, **kw):
    db.session.add(MembershipType(name=name, price=price, billing_frequency="yearly", **kw))
    db.session.commit()


def _payload(**kw):
    p = {"name": "Priya Das", "email": "priya@example.com", "phone": "41234567", "membership_type": "adult"}
    p.update(kw)
    return p


def _post(app, **kw):
    return app.test_client().post("/api/memberships/join", json=_payload(**kw))


def test_options_always_offer_pay_later_and_follow_the_switches():
    app = _new_app()
    with app.app_context():
        get_site_settings().vipps_qr_enabled = False
        db.session.commit()
        assert app.test_client().get("/api/memberships/join/options").get_json()["payment_methods"] == ["pay_later"]
        get_site_settings().vipps_qr_enabled = True
        db.session.commit()
        methods = app.test_client().get("/api/memberships/join/options").get_json()["payment_methods"]
        assert methods == ["vipps_qr", "pay_later"]
        db.drop_all()


def test_pay_later_creates_a_pending_request_with_periods_and_no_payment():
    app = _new_app()
    with app.app_context():
        _add_type()
        response = _post(app, payment_method="pay_later")
        assert response.status_code == 201
        assert response.get_json()["payment"] is None
        membership = Membership.query.one()
        assert membership.status == "pending"
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 1
        assert Payment.query.count() == 0
        db.drop_all()


def test_vipps_qr_creates_a_pending_payment_for_the_current_period_only():
    app = _new_app()
    with app.app_context():
        _add_type()
        get_site_settings().vipps_qr_enabled = True
        db.session.commit()
        response = _post(app, payment_method="vipps_qr")
        assert response.status_code == 201
        body = response.get_json()
        assert body["payment"]["status"] == "pending"
        assert body["payment"]["amount"] == 30000
        assert Membership.query.one().status == "pending"
        assert PaymentAllocation.query.count() == 1
        db.drop_all()


def test_vipps_app_returns_a_redirect_url_with_the_fee_on_top():
    app = _new_app()
    with app.app_context():
        _add_type()
        with patch("app.memberships.join_routes.vipps.is_public", return_value=True), patch(
            "app.memberships.join_routes.vipps.VippsClient"
        ) as client:
            client.return_value.create_payment.return_value = {"redirectUrl": "https://vipps.example/pay"}
            response = _post(app, payment_method="vipps_app")
        assert response.status_code == 201
        body = response.get_json()
        assert body["redirect_url"] == "https://vipps.example/pay"
        payment = Payment.query.one()
        assert payment.status == "initiated"
        assert payment.amount == 30000 + (payment.surcharge_amount or 0)
        db.drop_all()


def test_unavailable_method_and_bad_input_are_rejected():
    app = _new_app()
    with app.app_context():
        _add_type()
        get_site_settings().vipps_qr_enabled = False
        db.session.commit()
        assert _post(app, payment_method="vipps_qr").status_code == 400
        assert _post(app, name="").status_code == 400
        assert _post(app, email="nope").status_code == 400
        assert _post(app, phone="123").status_code == 400
        assert _post(app, membership_type="ghost").status_code == 400
        assert Member.query.count() == 0
        db.drop_all()


def test_an_email_with_an_active_membership_is_told_to_log_in():
    app = _new_app()
    with app.app_context():
        _add_type()
        member = Member(name="Priya Das", email="priya@example.com")
        db.session.add(member)
        db.session.commit()
        from datetime import date

        db.session.add(Membership(member_id=member.id, membership_type="adult", status="active", start_date=date.today()))
        db.session.commit()
        response = _post(app)
        assert response.status_code == 409
        db.drop_all()


def test_a_repeat_request_replaces_an_unpaid_pending_one():
    app = _new_app()
    with app.app_context():
        _add_type()
        _add_type(name="student", price=100)
        assert _post(app).status_code == 201
        assert _post(app, membership_type="student").status_code == 201
        assert [m.membership_type for m in Membership.query.all()] == ["student"]
        assert Member.query.count() == 1
        db.drop_all()


def test_a_request_with_a_payment_in_progress_is_not_replaced():
    app = _new_app()
    with app.app_context():
        _add_type()
        get_site_settings().vipps_qr_enabled = True
        db.session.commit()
        assert _post(app, payment_method="vipps_qr").status_code == 201
        assert _post(app).status_code == 409
        assert Payment.query.count() == 1
        db.drop_all()


def test_child_needs_a_parent_with_an_active_adult_membership():
    app = _new_app()
    with app.app_context():
        _add_type()
        _add_type(name="child", price=50)
        no_parent = app.test_client().post(
            "/api/memberships/join",
            json={"name": "Kid", "parent_email": "priya@example.com", "membership_type": "child"},
        )
        assert no_parent.status_code == 400
        assert "parent_email" in no_parent.get_json()["errors"]

        from datetime import date

        parent = Member(name="Priya Das", email="priya@example.com")
        db.session.add(parent)
        db.session.commit()
        db.session.add(Membership(member_id=parent.id, membership_type="adult", status="active", start_date=date.today()))
        db.session.commit()
        ok = app.test_client().post(
            "/api/memberships/join",
            json={"name": "Kid", "parent_email": "priya@example.com", "membership_type": "child"},
        )
        assert ok.status_code == 201
        child = Member.query.filter_by(name="Kid").one()
        assert child.parent_member_id == parent.id
        assert Membership.query.filter_by(member_id=child.id).one().status == "pending"
        db.drop_all()


def test_vipps_qr_charges_the_configured_convenience_fee_on_top():
    app = _new_app()
    with app.app_context():
        _add_type()
        settings = get_site_settings()
        settings.vipps_qr_enabled = True
        settings.vipps_qr_convenience_percent = 5
        db.session.commit()
        assert app.test_client().get("/api/memberships/join/options").get_json()["convenience_percent"]["vipps_qr"] == 5
        body = _post(app, payment_method="vipps_qr").get_json()
        assert body["payment"]["amount"] == 31500
        payment = Payment.query.one()
        assert payment.surcharge_amount == 1500
        assert PaymentAllocation.query.one().amount == 30000
        db.drop_all()
