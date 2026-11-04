"""Tests for bank transfer memberships (3 tests), e.g. periods response offers bank transfer only when it is usable; member reports a bank transfer and an admin confirms it; bank transfer is refused when it is not on."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.memberships.models import MembershipPeriod
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_membership_payment_routes import _make_member_with_active_membership


def _new_app(bank=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        settings = get_site_settings()
        settings.bank_transfer_enabled = bank
        settings.bank_account_holder = "Asha Club"
        settings.bank_account_number = "1234.56.78901"
        settings.bank_transfer_note = "Allow two days"
        db.session.commit()
    return app


def _call(app, method, path, token, **kw):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=auth_header(token), **kw)


def test_periods_response_offers_bank_transfer_only_when_it_is_usable():
    app = _new_app()
    with app.app_context():
        _, _, token = _make_member_with_active_membership()
        bank = _call(app, "get", "/api/memberships/me/periods", token).get_json()["bank"]
        assert bank["enabled"] is True and bank["details"]["holder"] == "Asha Club" and bank["details"]["iban"] == ""
        get_site_settings().bank_account_number = ""
        db.session.commit()
        off = _call(app, "get", "/api/memberships/me/periods", token).get_json()["bank"]
        assert off == {"enabled": False, "details": None}
        db.drop_all()


def test_member_reports_a_bank_transfer_and_an_admin_confirms_it():
    app = _new_app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id, status="unpaid").first()
        response = _call(app, "post", "/api/memberships/me/payments", token, json={"membership_period_ids": [period.id], "provider": "bank_transfer"})
        assert response.status_code == 200 and response.get_json()["payment"]["status"] == "pending"
        payment = Payment.query.one()
        assert payment.provider == "bank_transfer" and payment.payment_type == "membership"
        _, admin_token = make_user_and_token(role="admin", email="admin@example.com")
        done = _call(app, "post", f"/api/admin/payments/{payment.id}/confirm", admin_token)
        assert done.status_code == 200 and done.get_json()["status"] == "paid"
        db.session.refresh(period)
        assert period.status == "paid"
        db.drop_all()


def test_bank_transfer_is_refused_when_it_is_not_on():
    app = _new_app(bank=False)
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()
        period = MembershipPeriod.query.filter_by(membership_id=membership.id, status="unpaid").first()
        response = _call(app, "post", "/api/memberships/me/payments", token, json={"membership_period_ids": [period.id], "provider": "bank_transfer"})
        assert response.status_code == 400 and Payment.query.count() == 0
        db.drop_all()
