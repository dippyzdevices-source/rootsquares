"""Tests for order emails (14 tests), e.g. checkout sends order received email to customer; confirm payment sends awaiting verification email to admin; confirm payment sends payment notification email to customer."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    app.config["CONTACT_EMAIL"] = "bengali.culture.oslo@gmail.com"
    app.config["EMAIL_FROM"] = "BCA Oslo <noreply@bcaoslo.no>"
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_event(**overrides):
    from app.events.models import Event

    defaults = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": NOW + timedelta(days=10),
        "venue": "Oslo Concert Hall",
        "published": True,
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _add_type(event_id, **overrides):
    from app.tickets.models import TicketType

    defaults = {"event_id": event_id, "name": "Adult", "price": 15000}
    defaults.update(overrides)
    ticket_type = TicketType(**defaults)
    db.session.add(ticket_type)
    db.session.commit()
    return ticket_type


def _checkout(client, event, ticket_type, quantity=2):
    payload = {
        "event_id": event.id,
        "items": [{"ticket_type_id": ticket_type.id, "quantity": quantity}],
        "customer_name": "Priya Das",
        "customer_email": "priya@example.com",
        "customer_phone": "41234567",
    }
    return client.post("/api/orders", json=payload).get_json()


def _confirm_payment(client, order):
    return client.post(
        f"/api/orders/{order['order_number']}/confirm-payment",
        json={"email": order["customer_email"]},
    )


def test_checkout_sends_order_received_email_to_customer():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()

        _checkout(client, event, ticket_type)

        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 1
        assert sent[0]["to"] == "priya@example.com"
        assert "payment instructions" in sent[0]["subject"]
        assert "12345" in sent[0]["html"] and "24376" not in sent[0]["html"]  # the square's own Vipps number, never bca-oslo's
        assert "cid:vipps-qr" not in sent[0]["html"]  # no QR image: bca-oslo's would have sent payments to BCA
        assert len(sent[0]["attachments"]) == 1  # only the logo
        db.drop_all()


def test_confirm_payment_sends_awaiting_verification_email_to_admin():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)

        _confirm_payment(client, order)

        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 3  # order-received, customer payment-notification, admin awaiting-verification
        awaiting = sent[2]
        assert awaiting["to"] == ["bengali.culture.oslo@gmail.com"]
        assert order["order_number"] in awaiting["subject"]
        assert awaiting["reply_to"] == "priya@example.com"
        db.drop_all()


def test_confirm_payment_sends_payment_notification_email_to_customer():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)

        _confirm_payment(client, order)

        sent = app.extensions["email_service"].sent_emails
        notification = sent[1]
        assert notification["to"] == "priya@example.com"
        assert order["order_number"] in notification["subject"]
        assert "noted your payment" in notification["html"]
        db.drop_all()


def test_confirm_payment_skips_admin_email_when_contact_email_not_configured():
    app = _new_app()
    app.config["CONTACT_EMAIL"] = ""
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)

        response = _confirm_payment(client, order)

        assert response.status_code == 200
        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 2  # order-received, then the customer payment-notification email
        db.drop_all()


def test_mark_paid_sends_tickets_confirmed_email_with_qr_codes():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type, quantity=2)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            response = client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)

        assert response.status_code == 200
        sent = app.extensions["email_service"].sent_emails
        confirmed = sent[-1]
        assert confirmed["to"] == "priya@example.com"
        assert "confirmed" in confirmed["subject"]
        assert event.title in confirmed["subject"]
        assert confirmed["html"].count("cid:ticket-qr-") == 2

        qr_attachments = [
            a for a in confirmed["attachments"] if a.get("content_id", "").startswith("ticket-qr-")
        ]
        assert len(qr_attachments) == 2
        db.drop_all()


def test_mark_paid_tickets_confirmed_email_includes_location_directions_and_calendar_invite():
    app = _new_app()
    with app.app_context():
        event = _add_event(venue="Ulsrud Skole", address="Trondheimsveien 325, Oslo")
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type, quantity=1)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)

        confirmed = app.extensions["email_service"].sent_emails[-1]
        assert "Ulsrud Skole" in confirmed["html"]
        assert "Trondheimsveien 325, Oslo" in confirmed["html"]
        assert "google.com/maps/dir" in confirmed["html"]
        assert "calendar" in confirmed["html"].lower()
        assert "Ulsrud Skole" in confirmed["text"]
        assert "google.com/maps/dir" in confirmed["text"]

        ics_attachments = [a for a in confirmed["attachments"] if a["filename"].endswith(".ics")]
        assert len(ics_attachments) == 1
        ics = ics_attachments[0]
        assert ics["content_type"] == "text/calendar"
        ics_text = bytes(ics["content"]).decode("utf-8")
        assert "BEGIN:VCALENDAR" in ics_text
        assert f"SUMMARY:{event.title}" in ics_text
        assert "LOCATION:Ulsrud Skole\\, Trondheimsveien 325\\, Oslo" in ics_text
        db.drop_all()


def test_mark_paid_idempotent_replay_does_not_resend_tickets_email():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)
            sent_after_first = len(app.extensions["email_service"].sent_emails)
            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)

        assert len(app.extensions["email_service"].sent_emails) == sent_after_first
        db.drop_all()


def test_reject_sends_rejection_email_with_reason():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            response = client.post(
                f"/api/admin/orders/{order['id']}/reject",
                json={"reason": "No matching Vipps payment found."},
                headers=headers,
            )

        assert response.status_code == 200
        sent = app.extensions["email_service"].sent_emails
        rejected = sent[-1]
        assert rejected["to"] == "priya@example.com"
        assert order["order_number"] in rejected["subject"]
        assert "No matching Vipps payment found." in rejected["html"]
        db.drop_all()


def test_order_email_failure_does_not_block_checkout(monkeypatch):
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        def _raise(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(app.extensions["email_service"], "send_email", _raise)

        client = app.test_client()
        response = client.post(
            "/api/orders",
            json={
                "event_id": event.id,
                "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}],
                "customer_name": "Priya Das",
                "customer_email": "priya@example.com",
                "customer_phone": "41234567",
            },
        )

        assert response.status_code == 201
        db.drop_all()


_MULTI_ORIGIN = "https://bca-oslo.org,https://www.bca-oslo.org,http://localhost:5173"


def test_admin_email_link_uses_first_frontend_origin_only():
    app = _new_app()
    app.config["FRONTEND_ORIGIN"] = _MULTI_ORIGIN
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)

        _confirm_payment(client, order)

        awaiting = app.extensions["email_service"].sent_emails[2]
        assert f'href="https://bca-oslo.org/admin/orders/{order["id"]}"' in awaiting["html"]
        assert "bca-oslo.org,https" not in awaiting["html"]
        db.drop_all()


def test_order_received_email_link_uses_first_frontend_origin_only():
    app = _new_app()
    app.config["FRONTEND_ORIGIN"] = _MULTI_ORIGIN
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()

        _checkout(client, event, ticket_type)

        received = app.extensions["email_service"].sent_emails[0]
        assert "https://bca-oslo.org/orders/lookup?" in received["html"]
        assert "bca-oslo.org,https" not in received["html"]
        db.drop_all()


def test_cancel_paid_order_sends_cancellation_email_with_reason_and_does_not_resend_on_replay():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)
            before = len(app.extensions["email_service"].sent_emails)
            response = client.post(
                f"/api/admin/orders/{order['id']}/cancel",
                json={"reason": "Duplicate booking."},
                headers=headers,
            )
            sent = app.extensions["email_service"].sent_emails
            assert response.status_code == 200
            assert len(sent) == before + 1
            cancelled = sent[-1]
            assert cancelled["to"] == "priya@example.com"
            assert order["order_number"] in cancelled["subject"]
            assert "cancelled" in cancelled["subject"]
            assert "Duplicate booking." in cancelled["html"]

            client.post(f"/api/admin/orders/{order['id']}/cancel", json={"reason": "Duplicate booking."}, headers=headers)
            assert len(app.extensions["email_service"].sent_emails) == before + 1  # idempotent replay: no second email
        db.drop_all()


def test_resend_confirmation_sends_the_tickets_email_again_for_a_paid_order_only():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            # unpaid: nothing to send yet
            assert client.post(f"/api/admin/orders/{order['id']}/resend-confirmation", headers=headers).status_code == 409

            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)
            sent = app.extensions["email_service"].sent_emails
            before = len(sent)
            response = client.post(f"/api/admin/orders/{order['id']}/resend-confirmation", headers=headers)

            assert response.status_code == 200
            assert response.get_json() == {"sent_to": "priya@example.com"}
            assert len(sent) == before + 1
            again = sent[-1]
            assert again["to"] == "priya@example.com" and "confirmed" in again["subject"]
            assert len(again["attachments"]) >= 2  # the QR codes (one per ticket) travel with it

            assert client.post("/api/admin/orders/99999/resend-confirmation", headers=headers).status_code == 404
        db.drop_all()


def test_resend_confirmation_tells_the_admin_when_the_mail_service_fails_and_is_admin_only():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        order = _checkout(client, event, ticket_type)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _confirm_payment(client, order)
            client.post(f"/api/admin/orders/{order['id']}/mark-paid", headers=headers)
            with patch.object(app.extensions["email_service"], "send_email", side_effect=RuntimeError("smtp down")):
                response = client.post(f"/api/admin/orders/{order['id']}/resend-confirmation", headers=headers)
            assert response.status_code == 502
            assert "could not be sent" in response.get_json()["error"]

            _, member_token = make_user_and_token(role="member", email="m@example.com")
            denied = client.post(f"/api/admin/orders/{order['id']}/resend-confirmation", headers=auth_header(member_token))
            assert denied.status_code == 403
        db.drop_all()
