"""Tests for cash payments (9 tests), e.g. event offers cash only when the event and the site switch allow it; cash checkout creates a pending cash payment and sends the cash email; cash checkout is refused when the event or site does not allow it."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.payments.models import Payment
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_orders_checkout import _add_event, _add_type, _valid_payload


def _new_app(cash=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        from app.settings.models import get_site_settings

        settings = get_site_settings()
        settings.cash_enabled = cash
        settings.cash_ticket_note = "Site note: pay at the door."
        settings.cash_membership_note = "Pay a committee member."
        db.session.commit()
    return app


def _post_order(app, event, tt, method):
    with patch("app.orders.routes.send_cash_order_received_email") as cash_mail, patch(
        "app.orders.routes.send_order_received_email"
    ) as qr_mail:
        response = app.test_client().post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method=method))
    return response, cash_mail, qr_mail


def test_event_offers_cash_only_when_the_event_and_the_site_switch_allow_it():
    app = _new_app(cash=True)
    with app.app_context():
        both = _add_event(slug="cash-too", ticket_payment_methods="qr,app,cash")
        no_cash = _add_event(slug="no-cash", ticket_payment_methods="qr,app")
        client = app.test_client()
        detail = client.get("/api/events/cash-too").get_json()
        assert "cash" in detail["payment_methods"] and detail["cash_note"] == "Site note: pay at the door."
        assert "cash" not in client.get("/api/events/no-cash").get_json()["payment_methods"]
        assert client.get("/api/events/no-cash").get_json()["cash_note"] == ""

        both.cash_note = "Your place is not confirmed until you pay. Food is not guaranteed."
        db.session.commit()
        assert client.get("/api/events/cash-too").get_json()["cash_note"].startswith("Your place is not confirmed")

        from app.settings.models import get_site_settings

        get_site_settings().cash_enabled = False
        db.session.commit()
        assert "cash" not in client.get("/api/events/cash-too").get_json()["payment_methods"]
        db.drop_all()


def test_cash_checkout_creates_a_pending_cash_payment_and_sends_the_cash_email():
    app = _new_app()
    with app.app_context():
        event = _add_event(ticket_payment_methods="qr,cash")
        tt = _add_type(event.id)
        response, cash_mail, qr_mail = _post_order(app, event, tt, "cash")

        assert response.status_code == 201
        body = response.get_json()
        assert body["payment_status"] == "pending" and body["payment_method"] == "cash"
        assert body["cash_note"] == "Site note: pay at the door."
        payment = Payment.query.one()
        assert payment.provider == "cash" and payment.status == "pending"
        cash_mail.assert_called_once()
        qr_mail.assert_not_called()

        # no "I have paid" step for cash: an admin confirms it
        confirm = app.test_client().post(
            f"/api/orders/{body['order_number']}/confirm-payment", json={"email": "ola@example.com"}
        )
        assert confirm.status_code in (404, 409)
        db.drop_all()


def test_cash_checkout_is_refused_when_the_event_or_site_does_not_allow_it():
    app = _new_app(cash=True)
    with app.app_context():
        event = _add_event(ticket_payment_methods="qr")
        tt = _add_type(event.id)
        response, cash_mail, _ = _post_order(app, event, tt, "cash")
        assert response.status_code == 400 and "Vipps-QR" in response.get_json()["errors"]["payment_method"]
        cash_mail.assert_not_called()

        other = _add_event(slug="cash-event", ticket_payment_methods="qr,cash")
        tt2 = _add_type(other.id)
        from app.settings.models import get_site_settings

        get_site_settings().cash_enabled = False
        db.session.commit()
        response, _, _ = _post_order(app, other, tt2, "cash")
        assert response.status_code == 400
        db.drop_all()


def test_admin_mark_paid_can_record_how_it_was_really_paid():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()), patch(
        "app.orders.admin_routes.send_tickets_confirmed_email"
    ):
        event = _add_event(ticket_payment_methods="qr,cash")
        tt = _add_type(event.id)
        response, _, _ = _post_order(app, event, tt, "vipps_qr")
        assert response.status_code == 201
        order = Order.query.one()
        _, token = make_user_and_token(role="admin")
        h = auth_header(token)
        client = app.test_client()

        assert client.post(f"/api/admin/orders/{order.id}/mark-paid", headers=h, json={"payment_method": "bitcoin"}).status_code == 400
        paid = client.post(f"/api/admin/orders/{order.id}/mark-paid", headers=h, json={"payment_method": "cash"})
        assert paid.status_code == 200 and paid.get_json()["payment_status"] == "paid"
        payment = Payment.query.one()
        assert payment.provider == "cash" and payment.status == "paid"
        db.drop_all()


def test_event_cash_note_and_methods_are_saved_by_the_admin_and_copied_on_duplicate():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _, token = make_user_and_token(role="admin")
        h = auth_header(token)
        client = app.test_client()
        created = client.post(
            "/api/admin/events", headers=h,
            json={"title": "Puja", "slug": "puja", "event_type": "festival", "start_datetime": "2027-10-01T10:00:00Z",
                  "ticket_payment_methods": "cash,qr", "cash_note": "Pay before the day."},
        ).get_json()
        assert created["ticket_payment_methods"] == "qr,cash" and created["cash_note"] == "Pay before the day."
        assert client.patch(f"/api/admin/events/{created['id']}", headers=h, json={"ticket_payment_methods": "bitcoin"}).status_code == 400
        assert client.patch(f"/api/admin/events/{created['id']}", headers=h, json={"ticket_payment_methods": ""}).status_code == 400
        copy = client.post(f"/api/admin/events/{created['id']}/duplicate", headers=h).get_json()
        assert copy["cash_note"] == "Pay before the day." and copy["ticket_payment_methods"] == "qr,cash"
        db.drop_all()


def test_settings_save_the_cash_wording_with_a_length_limit():
    app = _new_app(cash=False)
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _, token = make_user_and_token(role="admin")
        h = auth_header(token)
        client = app.test_client()
        ok = client.patch("/api/admin/settings", headers=h, json={"cash_ticket_note": "  Not confirmed until paid.  "})
        assert ok.status_code == 200 and ok.get_json()["cash_ticket_note"] == "Not confirmed until paid."
        assert client.patch("/api/admin/settings", headers=h, json={"cash_membership_note": "x" * 1001}).status_code == 400
        db.drop_all()


def _member_with_periods():
    from tests.test_membership_payment_routes import _make_member_with_active_membership

    return _make_member_with_active_membership()


def test_member_can_choose_cash_only_while_it_is_switched_on_and_gets_the_wording():
    app = _new_app(cash=False)
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _, membership, token = _member_with_periods()
        h = auth_header(token)
        client = app.test_client()
        periods = client.get("/api/memberships/me/periods", headers=h).get_json()
        assert periods["cash"] == {"enabled": False, "note": "Pay a committee member."}
        period_id = periods["items"][0]["id"]

        refused = client.post("/api/memberships/me/payments", headers=h, json={"membership_period_ids": [period_id], "provider": "cash"})
        assert refused.status_code == 400

        from app.settings.models import get_site_settings

        get_site_settings().cash_enabled = True
        db.session.commit()
        assert client.get("/api/memberships/me/periods", headers=h).get_json()["cash"]["enabled"] is True
        ok = client.post("/api/memberships/me/payments", headers=h, json={"membership_period_ids": [period_id], "provider": "cash"})
        assert ok.status_code in (200, 201)
        payment = Payment.query.one()
        assert payment.provider == "cash" and payment.status == "pending"
        db.drop_all()


def test_membership_drive_records_cash_or_vipps_qr_as_chosen():
    from app.memberships.models import MembershipType

    app = _new_app(cash=False)
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        db.session.add(MembershipType(name="individual", price=100, billing_frequency="yearly"))
        db.session.commit()
        _, token = make_user_and_token(role="volunteer")
        h = auth_header(token)
        client = app.test_client()
        body = {"membership_type": "individual", "name": "Kari Hansen", "email": "kari@example.no", "phone": "91234567"}

        assert client.post("/api/admin/membership-drive/signup", headers=h, json={**body, "payment_method": "bitcoin"}).status_code == 400
        assert client.post("/api/admin/membership-drive/signup", headers=h, json={**body, "payment_method": "cash"}).status_code == 400

        from app.settings.models import get_site_settings

        get_site_settings().cash_enabled = True
        db.session.commit()
        assert client.post("/api/admin/membership-drive/signup", headers=h, json={**body, "payment_method": "cash"}).status_code == 201
        assert Payment.query.one().provider == "cash"
        db.drop_all()


def test_drive_options_tell_the_volunteer_whether_cash_is_on():
    app = _new_app(cash=True)
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _, token = make_user_and_token(role="volunteer")
        client = app.test_client()
        assert client.get("/api/admin/membership-drive/options", headers=auth_header(token)).get_json() == {"cash_enabled": True}
        _, member_token = make_user_and_token(role="member")
        assert client.get("/api/admin/membership-drive/options", headers=auth_header(member_token)).status_code == 403
        db.drop_all()
