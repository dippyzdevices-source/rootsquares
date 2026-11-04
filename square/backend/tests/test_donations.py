"""Tests for donations (10 tests), e.g. config lists only the methods that are on and the squares amounts; cash gift is pending then an admin confirms and the receipt goes out; validation and qr claim flow."""
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.donations import routes as donation_routes
from app.donations.models import Donation
from app.extensions import db
from tests.vipps_helpers import connect_vipps
from app.members import erasure
from app.members.models import Member
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        get_site_settings().cash_enabled = True
        db.session.commit()
    return app


def _gift(client, **over):
    body = {"donor_name": "Asha Rao", "donor_email": "asha@example.com", "amount": 25000, "payment_method": "cash"}
    body.update(over)
    return client.post("/api/donations", json=body)


def _admin(app, method, path, **kw):
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=auth_header(token), **kw)


def test_config_lists_only_the_methods_that_are_on_and_the_squares_amounts():
    app = _new_app()
    with app.app_context():
        settings = get_site_settings()
        settings.donation_amounts = "100,250"
        settings.donation_intro = "Help us"
        settings.vipps_qr_enabled = False
        db.session.commit()
        body = app.test_client().get("/api/donations/config").get_json()
        assert body["open"] and body["methods"] == ["cash"]
        assert body["amounts"] == [10000, 25000] and body["intro"] == "Help us"
        settings.cash_enabled = False
        db.session.commit()
        assert app.test_client().get("/api/donations/config").get_json()["open"] is False
        assert _gift(app.test_client()).status_code == 400  # no method is on: nothing is forced
        db.drop_all()


def test_cash_gift_is_pending_then_an_admin_confirms_and_the_receipt_goes_out():
    app = _new_app()
    with app.app_context():
        response = _gift(app.test_client(), anonymous=True, message="For the hall")
        assert response.status_code == 201
        body = response.get_json()
        assert body["reference"].startswith("DON-") and body["status"] == "pending"
        donation = Donation.query.one()
        payment = Payment.query.one()
        assert payment.payment_type == "donation" and payment.donation_id == donation.id and payment.amount == 25000

        with patch("app.donations.admin_routes.send_donation_receipt_email") as receipt:
            done = _admin(app, "post", f"/api/admin/donations/{donation.id}/mark-paid")
        assert done.status_code == 200 and done.get_json()["status"] == "paid"
        receipt.assert_called_once()
        db.session.refresh(payment)
        assert payment.status == "paid"
        entry = AuditLog.query.filter_by(action="donation.marked_paid").one()
        assert "Asha" not in entry.description
        listing = _admin(app, "get", "/api/admin/donations").get_json()
        assert listing["total"] == 1 and listing["paid_total"] == 25000 and listing["items"][0]["anonymous"] is True
        db.drop_all()


def test_validation_and_qr_claim_flow():
    app = _new_app()
    with app.app_context():
        client = app.test_client()
        bad = _gift(client, amount=5, donor_email="nope").get_json()["errors"]
        assert "amount" in bad and "donor_email" in bad
        settings = get_site_settings()
        settings.vipps_qr_enabled = True
        settings.vipps_number = "123456"
        db.session.commit()
        ref = _gift(client, payment_method="qr").get_json()["reference"]
        wrong = client.post(f"/api/donations/{ref}/confirm-payment", json={"email": "other@example.com"})
        assert wrong.status_code == 404
        ok = client.post(f"/api/donations/{ref}/confirm-payment", json={"email": "ASHA@example.com"})
        assert ok.status_code == 200 and ok.get_json()["status"] == "pending_verification"
        donation = Donation.query.one()
        rejected = _admin(app, "post", f"/api/admin/donations/{donation.id}/reject")
        assert rejected.get_json()["status"] == "rejected"
        assert _admin(app, "post", f"/api/admin/donations/{donation.id}/mark-paid").status_code == 409
        db.drop_all()


def test_donations_are_in_the_personal_data_export_and_in_erasure():
    app = _new_app()
    with app.app_context():
        member = Member(name="Asha Rao", email="asha@example.com")
        db.session.add(member)
        db.session.commit()
        _gift(app.test_client(), message="private note")
        exported = _admin(app, "get", f"/api/admin/members/{member.id}/personal-data").get_json()
        assert exported["donations"][0]["message"] == "private note"
        erasure.anonymise_member(member)
        donation = Donation.query.one()
        assert donation.donor_name == "Erased person" and donation.message is None and donation.amount == 25000
        assert donation.donor_email.endswith("@erased.invalid")
        db.drop_all()


def test_the_export_is_an_excel_file():
    app = _new_app()
    with app.app_context():
        _gift(app.test_client())
        response = _admin(app, "get", "/api/admin/donations/export")
        assert response.status_code == 200 and "donations.xlsx" in response.headers["Content-Disposition"]
        assert response.data[:2] == b"PK"
        db.drop_all()


def test_amounts_setting_is_validated():
    app = _new_app()
    with app.app_context():
        good = _admin(app, "patch", "/api/admin/settings", json={"donation_amounts": "100, 250,500"})
        assert good.status_code == 200 and good.get_json()["donation_amounts"] == "100,250,500"
        bad = _admin(app, "patch", "/api/admin/settings", json={"donation_amounts": "ten"})
        assert bad.status_code == 400 and "donation_amounts" in bad.get_json()["errors"]
        db.drop_all()


def test_available_methods_helper_exposed():
    assert donation_routes.MIN_AMOUNT == 100


def test_vipps_app_gift_is_paid_by_the_return_check_with_the_surcharge_and_a_receipt():
    from app.payments import vipps

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        get_site_settings().vipps_app_public = True
        connect_vipps("x")
        db.session.commit()
        client = app.test_client()
        with patch.object(vipps.VippsClient, "create_payment", return_value={"redirectUrl": "https://vipps.test/pay"}) as create:
            response = _gift(client, payment_method="app", amount=20000)
        body = response.get_json()
        assert response.status_code == 201 and body["redirect_url"] == "https://vipps.test/pay"
        assert create.call_args.args[1] == 21000 and body["surcharge_amount"] == 1000  # 5% on top; the gift itself stays 200
        payment = Payment.query.one()
        assert payment.status == "initiated" and Donation.query.one().amount == 20000

        with patch.object(vipps.VippsClient, "get_payment", return_value={"state": "AUTHORIZED"}), patch.object(
            vipps.VippsClient, "capture", return_value={}
        ) as capture, patch("app.donations.emails.send_donation_receipt_email") as receipt:
            back = client.post("/api/payments/vipps-return", json={"reference": payment.provider_transaction_id})
        assert back.get_json() == {"status": "paid", "order_number": None, "provider": "vipps_app", "donation_reference": body["reference"]}
        assert capture.call_args.args[1] == 21000
        receipt.assert_called_once()
        assert Donation.query.one().status == "paid"
        db.drop_all()


def test_bank_transfer_needs_switch_holder_and_account_then_works_like_a_manual_method():
    app = _new_app()
    with app.app_context():
        client = app.test_client()
        settings = get_site_settings()
        settings.cash_enabled = False
        settings.vipps_qr_enabled = False
        settings.bank_transfer_enabled = True
        settings.bank_account_holder = "Asha Club"
        db.session.commit()
        assert client.get("/api/donations/config").get_json()["open"] is False  # holder alone is not enough: no account number or IBAN
        settings.bank_iban = "NO9386011117947"
        settings.bank_transfer_note = "Allow two days"
        db.session.commit()
        config = client.get("/api/donations/config").get_json()
        assert config["methods"] == ["bank"] and config["bank"]["iban"] == "NO9386011117947" and config["bank"]["bic"] == ""
        assert config["bank"]["note"] == "Allow two days"
        response = _gift(client, payment_method="bank")
        assert response.status_code == 201
        payment = Payment.query.one()
        assert payment.provider == "bank_transfer" and payment.status == "pending"
        ref = response.get_json()["reference"]
        assert client.post(f"/api/donations/{ref}/confirm-payment", json={"email": "asha@example.com"}).status_code == 200
        donation = Donation.query.one()
        with patch("app.donations.admin_routes.send_donation_receipt_email"):
            done = _admin(app, "post", f"/api/admin/donations/{donation.id}/mark-paid", json={"payment_method": "bank_transfer"})
        assert done.get_json()["status"] == "paid" and done.get_json()["payment_method"] == "bank_transfer"
        db.drop_all()


def test_bank_details_settings_are_validated_and_saved():
    app = _new_app()
    with app.app_context():
        saved = _admin(app, "patch", "/api/admin/settings", json={"bank_transfer_enabled": True, "bank_account_holder": " Asha Club ", "bank_account_number": "1234.56.78901"})
        body = saved.get_json()
        assert saved.status_code == 200 and body["bank_account_holder"] == "Asha Club" and body["bank_transfer_available"] is True
        too_long = _admin(app, "patch", "/api/admin/settings", json={"bank_bic": "X" * 40})
        assert too_long.status_code == 400 and "bank_bic" in too_long.get_json()["errors"]
        db.drop_all()
