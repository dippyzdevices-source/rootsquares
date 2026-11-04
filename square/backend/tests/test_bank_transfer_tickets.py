"""Tests for bank transfer tickets (5 tests), e.g. event offers bank transfer only when event and settings allow it; bank checkout creates a pending manual payment and mails the details; bank checkout is refused when the event does not offer it."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.orders.models import Order
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_orders_checkout import _add_event, _add_type, _valid_payload


def _new_app(bank=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        settings = get_site_settings()
        settings.bank_transfer_enabled = bank
        settings.bank_account_holder = "Asha Club"
        settings.bank_iban = "NO9386011117947"
        settings.bank_transfer_note = "Allow two days"
        db.session.commit()
    return app


def test_event_offers_bank_transfer_only_when_event_and_settings_allow_it():
    app = _new_app()
    with app.app_context():
        _add_event(slug="with-bank", ticket_payment_methods="qr,bank")
        _add_event(slug="without-bank", ticket_payment_methods="qr")
        client = app.test_client()
        detail = client.get("/api/events/with-bank").get_json()
        assert "bank" in detail["payment_methods"] and detail["bank"]["iban"] == "NO9386011117947"
        other = client.get("/api/events/without-bank").get_json()
        assert "bank" not in other["payment_methods"] and other["bank"] is None
        get_site_settings().bank_transfer_enabled = False
        db.session.commit()
        assert "bank" not in client.get("/api/events/with-bank").get_json()["payment_methods"]
        db.drop_all()


def test_bank_checkout_creates_a_pending_manual_payment_and_mails_the_details():
    app = _new_app()
    with app.app_context():
        event = _add_event(ticket_payment_methods="qr,bank")
        tt = _add_type(event.id, price=15000)
        with patch("app.orders.routes.send_bank_order_received_email") as mail:
            response = app.test_client().post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method="bank_transfer"))
        assert response.status_code == 201
        body = response.get_json()
        assert body["payment_method"] == "bank_transfer" and body["payment_status"] == "pending"
        assert body["bank"]["holder"] == "Asha Club" and body["bank"]["bic"] == ""
        payment = Payment.query.one()
        assert payment.provider == "bank_transfer" and payment.status == "pending"
        mail.assert_called_once()
        db.drop_all()


def test_bank_checkout_is_refused_when_the_event_does_not_offer_it():
    app = _new_app()
    with app.app_context():
        event = _add_event(ticket_payment_methods="qr")
        tt = _add_type(event.id)
        response = app.test_client().post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method="bank_transfer"))
        assert response.status_code == 400 and "payment_method" in response.get_json()["errors"]
        assert Order.query.count() == 0
        db.drop_all()


def test_buyer_reports_payment_and_admin_marks_it_paid_with_bank_transfer():
    app = _new_app()
    with app.app_context():
        event = _add_event(ticket_payment_methods="bank")
        tt = _add_type(event.id)
        client = app.test_client()
        with patch("app.orders.routes.send_bank_order_received_email"):
            order = client.post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method="bank_transfer")).get_json()
        email = order["customer_email"]
        with patch("app.orders.routes.send_payment_notification_received_email"), patch("app.orders.routes.send_order_awaiting_verification_email"):
            reported = client.post(f"/api/orders/{order['order_number']}/confirm-payment", json={"email": email})
        assert reported.status_code == 200
        _, token = make_user_and_token(role="admin", email="admin@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()), patch("app.orders.admin_routes.send_tickets_confirmed_email", create=True):
            done = client.post(f"/api/admin/orders/{order['id']}/mark-paid", json={"payment_method": "bank_transfer"}, headers=auth_header(token))
        assert done.status_code == 200 and done.get_json()["payment_status"] == "paid"
        assert Payment.query.one().provider == "bank_transfer"
        db.drop_all()


def test_the_bank_email_lists_the_details_and_the_order_number_and_skips_empty_fields():
    app = _new_app()
    with app.app_context():
        event = _add_event(ticket_payment_methods="bank")
        tt = _add_type(event.id)
        from app.email.templates import render_bank_order_received_email
        from app.payments.bank import bank_details

        with patch("app.orders.routes.send_bank_order_received_email"):
            body = app.test_client().post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method="bank_transfer")).get_json()
        order = Order.query.first()
        html_out, text, _ = render_bank_order_received_email(order=order, event=event, bank=bank_details(get_site_settings()), order_url="http://x/o")
        assert "Asha Club" in text and "NO9386011117947" in text and order.order_number in text and "BIC" not in text and "Allow two days" in text
        assert "NO9386011117947" in html_out
        db.drop_all()
