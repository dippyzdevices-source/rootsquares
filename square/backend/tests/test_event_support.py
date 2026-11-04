"""Tests for event support (9 tests), e.g. options report whether the event is open and the methods; an expired or draft event accepts nothing; a qr donation is saved pending with no fee and no payment row."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app import create_app
from app.accounting.models import EventContribution
from app.extensions import db
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_admin_accounting_routes import NOW, _add_event

JWKS = "app.auth.jwt_verification._get_jwks_client"


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _base(slug="durga-puja-2026"):
    return f"/api/events/{slug}/support"


def _settings(qr=True):
    s = get_site_settings()
    s.vipps_qr_enabled = qr
    db.session.commit()


def _post(app, path, **body):
    return app.test_client().post(_base() + path, json=body)


def test_options_report_whether_the_event_is_open_and_the_methods():
    app = _new_app()
    with app.app_context():
        _add_event()
        _settings(qr=True)
        body = app.test_client().get(_base() + "/options").get_json()
        assert body == {"open": True, "donations_open": True, "sponsorships_open": True, "payment_methods": ["vipps_qr"]}
        _add_event(slug="old", title="Old", start_datetime=NOW - timedelta(days=5))
        old = app.test_client().get(_base("old") + "/options").get_json()
        assert old["open"] is False and old["donations_open"] is False
        db.drop_all()


def test_an_expired_or_draft_event_accepts_nothing():
    app = _new_app()
    with app.app_context():
        _add_event(slug="old", title="Old", start_datetime=NOW - timedelta(days=5))
        _add_event(slug="draft", title="Draft", published=False)
        _settings()
        client = app.test_client()
        assert client.post(_base("old") + "/donations", json={"amount": 5000, "payment_method": "vipps_qr"}).status_code == 409
        assert client.post(_base("old") + "/sponsorships", json={}).status_code == 409
        assert client.post(_base("draft") + "/donations", json={}).status_code == 404
        assert EventContribution.query.count() == 0
        db.drop_all()


def test_a_qr_donation_is_saved_pending_with_no_fee_and_no_payment_row():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _settings()
        response = _post(app, "/donations", name="", amount=25000, payment_method="vipps_qr")
        assert response.status_code == 201
        donation = EventContribution.query.one()
        assert (donation.event_id, donation.kind, donation.name, donation.amount, donation.status) == (
            event.id, "donation", "Anonymous", 25000, "pending",
        )
        assert Payment.query.count() == 0
        db.drop_all()


def test_donation_validation():
    app = _new_app()
    with app.app_context():
        _add_event()
        _settings(qr=False)
        assert _post(app, "/donations", amount=5000, payment_method="vipps_qr").status_code == 400  # method off
        _settings(qr=True)
        assert _post(app, "/donations", amount=100, payment_method="vipps_qr").status_code == 400  # below 10 kr
        assert _post(app, "/donations", amount=5000, payment_method="vipps_qr", email="nope").status_code == 400
        assert EventContribution.query.count() == 0
        db.drop_all()


def test_a_vipps_app_donation_charges_exactly_the_amount_and_becomes_paid_when_vipps_confirms():
    app = _new_app()
    with app.app_context():
        _add_event()
        client_mock = MagicMock()
        client_mock.create_payment.return_value = {"redirectUrl": "https://vipps.example/pay"}
        client_mock.get_payment.return_value = {"state": "AUTHORIZED"}
        with patch("app.accounting.support_routes.vipps.is_public", return_value=True), patch(
            "app.accounting.support_routes.vipps.VippsClient", return_value=client_mock
        ), patch("app.payments.vipps.VippsClient", return_value=client_mock), patch(
            "app.payments.vipps.is_enabled", return_value=True
        ):
            response = _post(app, "/donations", name="Maya", amount=10000, payment_method="vipps_app")
            assert response.status_code == 201
            assert response.get_json()["redirect_url"] == "https://vipps.example/pay"
            payment = Payment.query.one()
            assert (payment.payment_type, payment.amount, payment.surcharge_amount, payment.status) == (
                "event_donation", 10000, None, "initiated",
            )
            assert EventContribution.query.one().status == "pending"

            ref = payment.provider_transaction_id
            result = app.test_client().post("/api/payments/vipps-return", json={"reference": ref})
            assert result.status_code == 200
        db.session.expire_all()
        assert Payment.query.one().status == "paid"
        assert EventContribution.query.one().status == "paid"
        client_mock.capture.assert_called_once()
        db.drop_all()


def test_a_failed_vipps_donation_is_not_counted():
    app = _new_app()
    with app.app_context():
        _add_event()
        client_mock = MagicMock()
        client_mock.create_payment.return_value = {"redirectUrl": "https://vipps.example/pay"}
        client_mock.get_payment.return_value = {"state": "ABORTED"}
        with patch("app.accounting.support_routes.vipps.is_public", return_value=True), patch(
            "app.accounting.support_routes.vipps.VippsClient", return_value=client_mock
        ), patch("app.payments.vipps.VippsClient", return_value=client_mock):
            _post(app, "/donations", amount=10000, payment_method="vipps_app")
            ref = Payment.query.one().provider_transaction_id
            app.test_client().post("/api/payments/vipps-return", json={"reference": ref})
        db.session.expire_all()
        assert EventContribution.query.one().status == "failed"
        db.drop_all()


def test_a_sponsorship_enquiry_is_saved_pending_with_contact_details_and_requirements():
    app = _new_app()
    with app.app_context():
        _add_event()
        bad = _post(app, "/sponsorships", name="Acme AS")
        assert bad.status_code == 400 and {"contact_name", "email"} <= set(bad.get_json()["errors"])
        ok = _post(
            app, "/sponsorships", name="Acme AS", contact_name="Ola", email="ola@acme.no", phone="41234567",
            website="https://acme.no", requirements="Logo on the stage banner", amount=500000,
        )
        assert ok.status_code == 201
        row = EventContribution.query.one()
        assert (row.kind, row.status, row.contact_name, row.requirements, row.amount) == (
            "sponsorship", "pending", "Ola", "Logo on the stage banner", 500000,
        )
        assert _post(app, "/sponsorships", name="B", contact_name="C", email="c@d.no", website="acme.no").status_code == 400
        db.drop_all()


def test_donation_processing_fee_is_an_expense_and_pending_ones_do_not_count():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        payment = Payment(
            payment_type="event_donation", provider="vipps_app", amount=10000, status="paid",
            processing_fee_amount=399,
        )
        db.session.add(payment)
        db.session.commit()
        db.session.add_all(
            [
                EventContribution(event_id=event.id, kind="donation", name="A", amount=10000, date=date.today(), status="paid", payment_id=payment.id),
                EventContribution(event_id=event.id, kind="donation", name="B", amount=7777, date=date.today(), status="pending"),
                EventContribution(event_id=event.id, kind="sponsorship", name="C", amount=None, date=date.today(), status="pending"),
            ]
        )
        db.session.commit()
        _, token = make_user_and_token(role="admin")
        with patch(JWKS, return_value=FakeJWKClient()):
            summary = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=auth_header(token)
            ).get_json()
        assert summary["donations_total"] == 10000
        assert summary["collection_total"] == 10000
        assert summary["processing_fees_total"] == 399
        assert summary["net_total"] == 10000 - 399
        assert summary["pending_contributions"] == 2
        db.drop_all()


def test_admin_marks_a_pending_sponsorship_received_only_with_an_amount():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        row = EventContribution(event_id=event.id, kind="sponsorship", name="Acme", amount=None, date=date.today(), status="pending")
        db.session.add(row)
        db.session.commit()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch(JWKS, return_value=FakeJWKClient()):
            client = app.test_client()
            url = f"/api/admin/accounting/contributions/{row.id}"
            assert client.patch(url, json={"status": "paid"}, headers=headers).status_code == 400
            ok = client.patch(url, json={"status": "paid", "amount": 300000}, headers=headers)
            assert ok.status_code == 200 and ok.get_json()["status"] == "paid"
        db.drop_all()
