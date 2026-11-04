"""Card payments through Stripe with the square's own keys (W16-R6): connect, tickets, memberships, the webhook, refunds, and the no-fallback rule."""

import hashlib
import hmac
import json
import time
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.payments import credentials, gateway, stripe_gateway
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_membership_payment_routes import _make_member_with_active_membership
from tests.test_orders_checkout import _add_event, _add_type, _valid_payload

KEY = "rk_test_51AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
WHSEC = "whsec_test_secret_value"


def _connect_stripe(webhook_secret: str = WHSEC) -> None:
    credentials.save("stripe", {"secret_key": KEY, "webhook_secret": webhook_secret}, mode="test", hint={"key_last4": "6789", "restricted": True})


def _app(connected=True, enabled=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        if connected:
            _connect_stripe()
        get_site_settings().stripe_enabled = enabled
        db.session.commit()
    return app


def _patches(state="CREATED", session_id="cs_test_1"):
    return (
        patch.object(stripe_gateway.StripeClient, "create_payment", return_value={"id": session_id, "redirectUrl": "https://checkout.stripe.test/pay"}),
        patch.object(stripe_gateway.StripeClient, "get_payment", return_value={"state": state}),
        patch.object(stripe_gateway.StripeClient, "cancel", return_value={}),
        patch.object(stripe_gateway.StripeClient, "refund", return_value={"id": "re_1"}),
    )


def _checkout(app, event, ticket_type):
    return app.test_client().post("/api/orders", json=_valid_payload(event.id, ticket_type.id, payment_method="stripe"))


def _signed(payload: dict, secret: str = WHSEC) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


# ---- connecting ---------------------------------------------------------------------------------------------------------------------------------
def _call(app, method, path="/stripe", **kw):
    _, token = make_user_and_token(role="admin", email="owner@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(f"/api/admin/payments/providers{path}", headers=auth_header(token), **kw)


def test_connect_stores_the_key_encrypted_and_never_returns_it():
    app = _app(connected=False)
    with app.app_context(), patch.object(stripe_gateway.StripeClient, "check"), patch.object(stripe_gateway.StripeClient, "register_webhook", return_value={"secret": WHSEC}):
        res = _call(app, "put", json={"secret_key": KEY})
        assert res.status_code == 200 and KEY not in res.get_data(as_text=True)
        view = res.get_json()["providers"]["stripe"]
        assert view["connected"] is True and view["mode"] == "test" and view["hint"] == {"key_last4": "6789", "restricted": True}
        row = credentials.get_secret("stripe")
        assert row[0]["secret_key"] == KEY
        from app.payments.models import PaymentCredential

        assert KEY not in PaymentCredential.query.filter_by(provider="stripe").one().ciphertext
        assert stripe_gateway.is_enabled() is True


def test_a_value_that_is_not_a_stripe_key_is_refused_before_calling_stripe():
    app = _app(connected=False)
    with app.app_context(), patch.object(stripe_gateway.StripeClient, "check") as check:
        res = _call(app, "put", json={"secret_key": "pk_test_publishable"})
        assert res.status_code == 400 and "secret_key" in res.get_json()["errors"]
        check.assert_not_called()


def test_a_key_stripe_refuses_or_that_lacks_a_permission_is_not_saved_and_the_message_is_plain():
    app = _app(connected=False)
    with app.app_context():
        for code, word in ((401, "did not accept"), (403, "missing a permission")):
            with patch.object(stripe_gateway.StripeClient, "check", side_effect=stripe_gateway.StripeError("x", code)):
                res = _call(app, "put", json={"secret_key": KEY})
            assert res.status_code == 422 and word in res.get_json()["errors"]["_"] and KEY not in res.get_data(as_text=True)
        assert stripe_gateway.is_enabled() is False


def test_a_typed_signing_secret_is_stored_and_checked():
    app = _app(connected=False)
    with app.app_context(), patch.object(stripe_gateway.StripeClient, "check"):
        bad = _call(app, "put", json={"secret_key": KEY, "webhook_secret": "nope"})
        assert bad.status_code == 400 and "webhook_secret" in bad.get_json()["errors"]
        ok = _call(app, "put", json={"secret_key": KEY, "webhook_secret": WHSEC})
        assert ok.status_code == 200 and WHSEC not in ok.get_data(as_text=True)
        assert credentials.get_secret("stripe")[0]["webhook_secret"] == WHSEC
        assert ok.get_json()["providers"]["stripe"]["webhook_registered"] is True


def test_disconnect_removes_the_key():
    app = _app()
    with app.app_context():
        assert _call(app, "delete").get_json()["providers"]["stripe"]["connected"] is False
        assert stripe_gateway.is_enabled() is False
        from app.settings.models import get_site_settings

        assert get_site_settings().stripe_enabled is False  # disconnecting switches the method off


# ---- availability: no fallback, an admin switch, a currency Stripe takes -----------------------------------------------------------------------
def test_card_is_offered_only_when_connected_switched_on_and_in_a_supported_currency():
    for connected, enabled in ((False, True), (True, False)):
        app = _app(connected=connected, enabled=enabled)
        with app.app_context():
            assert stripe_gateway.is_public() is False
            assert gateway.is_public("stripe") is False
            assert app.test_client().get("/api/payments/stripe").get_json()["enabled"] is False
    app = _app()
    with app.app_context():
        assert stripe_gateway.is_public() is True
        with patch("app.common.site.site_currency", return_value="JPY"):
            assert stripe_gateway.is_public() is False  # zero-decimal currencies are not supported


def test_nothing_is_read_from_the_environment():
    app = _app(connected=False)
    app.config.update(STRIPE_SECRET_KEY=KEY, STRIPE_API_KEY=KEY)
    with app.app_context():
        assert stripe_gateway.is_enabled() is False
        try:
            stripe_gateway.StripeClient()
        except stripe_gateway.StripeError:
            pass
        else:
            raise AssertionError("a client was made without stored keys")


# ---- tickets ------------------------------------------------------------------------------------------------------------------------------------
def test_ticket_checkout_with_card_charges_total_plus_the_card_fee_and_returns_the_stripe_page():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        get_site_settings().stripe_convenience_percent = 3
        db.session.commit()
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id, price=10000)
        create, get, can, ref = _patches()
        with create as create_mock, get, can, ref:
            res = _checkout(app, event, tt)
        assert res.status_code == 201
        body = res.get_json()
        assert body["redirect_url"] == "https://checkout.stripe.test/pay" and body["payment_status"] == "pending"
        fee = body["surcharge_amount"]
        assert fee == (body["total_amount"] * 3 + 50) // 100 and create_mock.call_args.args[1] == body["total_amount"] + fee
        assert "{CHECKOUT_SESSION_ID}" in create_mock.call_args.args[2]  # Stripe puts the real session id back into the return link
        payment = Payment.query.one()
        assert payment.provider == "stripe" and payment.provider_transaction_id == "cs_test_1" and payment.status == "initiated"
        assert Order.query.one().payment_status == "pending"


def test_a_card_checkout_is_refused_when_the_event_does_not_offer_it():
    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "cash"
        tt = _add_type(event.id)
        res = _checkout(app, event, tt)
        assert res.status_code == 400 and "only accepts" in json.dumps(res.get_json())


def test_card_checkout_is_unavailable_without_a_connected_account():
    from app.orders.models import Order

    app = _app(connected=False)
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        res = _checkout(app, event, tt)
        assert res.status_code == 503 and "Card payment" in res.get_json()["error"]
        assert Order.query.count() == 0


def test_no_order_is_left_behind_if_stripe_refuses():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        with patch.object(stripe_gateway.StripeClient, "create_payment", side_effect=stripe_gateway.StripeError("boom")):
            res = _checkout(app, event, tt)
        assert res.status_code == 502 and "card payment" in res.get_json()["error"]
        assert Order.query.count() == 0 and Payment.query.count() == 0


def test_return_from_stripe_marks_the_order_paid_issues_tickets_once():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        create, get, can, ref = _patches("AUTHORIZED")
        with create, get, can, ref, patch("app.orders.emails.send_tickets_confirmed_email") as email:
            _checkout(app, event, tt)
            client = app.test_client()
            first = client.post("/api/payments/vipps-return", json={"reference": "cs_test_1"})
            second = client.post("/api/payments/vipps-return", json={"reference": "cs_test_1"})
        assert first.get_json()["status"] == "paid" and second.get_json()["status"] == "paid"
        order = Order.query.one()
        assert order.payment_status == "paid" and Ticket.query.count() == 2 and email.call_count == 1


def test_a_paid_session_for_an_order_that_was_rejected_meanwhile_is_given_back():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        create, get, can, ref = _patches("AUTHORIZED")
        with create, get, can as cancel_mock, ref:
            _checkout(app, event, tt)
            Order.query.one().payment_status = "rejected"
            db.session.commit()
            res = app.test_client().post("/api/payments/vipps-return", json={"reference": "cs_test_1"})
        assert res.get_json()["status"] == "cancelled" and Ticket.query.count() == 0
        cancel_mock.assert_called_once()  # the Stripe client turns this into a refund for a paid session


# ---- the webhook --------------------------------------------------------------------------------------------------------------------------------
def test_the_webhook_needs_this_squares_signing_secret_and_then_settles_the_payment():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        create, get, can, ref = _patches("AUTHORIZED")
        with create, get, can, ref, patch("app.orders.emails.send_tickets_confirmed_email"):
            _checkout(app, event, tt)
            payload = {"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1", "object": "checkout.session"}}}
            client = app.test_client()
            bad_body, bad_headers = _signed(payload, "whsec_someone_elses")
            assert client.post("/api/webhooks/stripe", data=bad_body, headers=bad_headers).status_code == 401
            assert Order.query.one().payment_status == "pending"
            body, headers = _signed(payload)
            assert client.post("/api/webhooks/stripe", data=body, headers=headers).status_code == 200
            assert client.post("/api/webhooks/stripe", data=body, headers=headers).status_code == 200  # idempotent
        assert Order.query.one().payment_status == "paid"


def test_the_webhook_is_refused_when_no_signing_secret_is_stored():
    app = _app(connected=False)
    with app.app_context():
        _connect_stripe(webhook_secret="")
        body, headers = _signed({"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {"id": "cs_x"}}})
        assert app.test_client().post("/api/webhooks/stripe", data=body, headers=headers).status_code == 401


# ---- memberships and refunds --------------------------------------------------------------------------------------------------------------------
def _start_membership(app, token, period_ids):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().post("/api/memberships/me/payments", json={"membership_period_ids": period_ids, "provider": "stripe"}, headers=auth_header(token))


def test_a_member_pays_a_membership_by_card_and_an_admin_can_refund_it_through_stripe():
    from app.memberships.models import MembershipPeriod

    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership(price=200)
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        period = MembershipPeriod.query.filter_by(membership_id=membership.id).order_by(MembershipPeriod.period_start).first()
        create, get, can, ref = _patches("AUTHORIZED")
        with create, get, can, ref as refund_mock:
            res = _start_membership(app, token, [period.id])
            assert res.status_code == 200 and res.get_json()["redirect_url"] == "https://checkout.stripe.test/pay"
            payment_id = res.get_json()["payment"]["id"]
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                client = app.test_client()
                client.post(f"/api/memberships/me/payments/{payment_id}/refresh", headers=auth_header(token))
                listing = client.get("/api/admin/payments", headers=auth_header(admin_token)).get_json()["items"][0]
                refund = client.post(f"/api/admin/payments/{payment_id}/refund", json={}, headers=auth_header(admin_token))
        assert listing["refund_mode"] == "stripe"
        assert refund.status_code == 200 and refund_mock.call_args.args == ("cs_test_1", db.session.get(Payment, payment_id).amount)
        assert db.session.get(Payment, payment_id).status == "refunded"


def test_the_periods_answer_lists_the_card_method_with_its_fee():
    app = _app()
    with app.app_context():
        get_site_settings().stripe_convenience_percent = 2
        db.session.commit()
        _, membership, token = _make_member_with_active_membership(price=200)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            body = app.test_client().get("/api/memberships/me/periods", headers=auth_header(token)).get_json()
        assert body["stripe"] == {"enabled": True, "surcharge_percent": 2.0}


def test_a_visitor_can_join_and_pay_by_card_from_the_membership_page():
    from app.memberships.models import MembershipType

    app = _app()
    with app.app_context():
        get_site_settings().stripe_convenience_percent = 2
        db.session.add(MembershipType(name="adult", price=300, billing_frequency="yearly"))
        db.session.commit()
        options = app.test_client().get("/api/memberships/join/options").get_json()
        assert "stripe" in options["payment_methods"] and options["convenience_percent"]["stripe"] == 2.0
        create, get, can, ref = _patches()
        with create as create_mock, get, can, ref:
            res = app.test_client().post(
                "/api/memberships/join",
                json={"name": "Priya Das", "email": "priya@example.com", "phone": "41234567", "membership_type": "adult", "payment_method": "stripe"},
            )
        assert res.status_code == 201 and res.get_json()["redirect_url"] == "https://checkout.stripe.test/pay"
        payment = Payment.query.one()
        assert payment.provider == "stripe" and payment.provider_transaction_id == "cs_test_1" and payment.status == "initiated"
        assert payment.amount == 30000 + payment.surcharge_amount and payment.surcharge_amount == 600
        assert "kind=membership" in create_mock.call_args.args[2] and "{CHECKOUT_SESSION_ID}" in create_mock.call_args.args[2]


# ---- phase 3: donations and event donations by card ---------------------------------------------------------------------------------------------
def test_a_donation_can_be_given_by_card_with_the_fee_and_a_receipt():
    from app.donations.models import Donation

    app = _app()
    with app.app_context():
        get_site_settings().stripe_convenience_percent = 3
        db.session.commit()
        client = app.test_client()
        config = client.get("/api/donations/config").get_json()
        assert "card" in config["methods"] and config["card_surcharge_percent"] == 3.0 and config["open"] is True
        create, get, can, ref = _patches("AUTHORIZED")
        with create as create_mock, get, can, ref:
            res = client.post("/api/donations", json={"donor_name": "Asha Rao", "donor_email": "asha@example.com", "amount": 20000, "payment_method": "card"})
            body = res.get_json()
            assert res.status_code == 201 and body["redirect_url"] == "https://checkout.stripe.test/pay"
            assert create_mock.call_args.args[1] == 20600 and body["surcharge_amount"] == 600  # the gift stays 200, the fee is on top
            assert "/donate/thanks?ref={CHECKOUT_SESSION_ID}" in create_mock.call_args.args[2]
            payment = Payment.query.one()
            assert payment.provider == "stripe" and payment.payment_type == "donation" and payment.status == "initiated"
            with patch("app.donations.emails.send_donation_receipt_email") as receipt:
                back = client.post("/api/payments/vipps-return", json={"reference": "cs_test_1"})
        assert back.get_json() == {"status": "paid", "order_number": None, "provider": "stripe", "donation_reference": body["reference"]}
        receipt.assert_called_once()
        assert Donation.query.one().status == "paid"


def test_card_is_not_offered_for_donations_until_connected_and_switched_on():
    app = _app(connected=False)
    with app.app_context():
        assert "card" not in app.test_client().get("/api/donations/config").get_json()["methods"]
        res = app.test_client().post("/api/donations", json={"donor_name": "A", "donor_email": "a@example.com", "amount": 5000, "payment_method": "card"})
        assert res.status_code == 400


def test_an_event_donation_by_card_counts_once_stripe_confirms_it():
    from app.accounting.models import EventContribution
    from tests.test_admin_accounting_routes import _add_event

    app = _app()
    with app.app_context():
        _add_event()
        client = app.test_client()
        base = "/api/events/durga-puja-2026/support"
        assert "stripe" in client.get(base + "/options").get_json()["payment_methods"]
        create, get, can, ref = _patches("AUTHORIZED")
        with create as create_mock, get, can, ref:
            res = client.post(base + "/donations", json={"name": "Priya", "amount": 15000, "payment_method": "stripe"})
            assert res.status_code == 201 and res.get_json()["redirect_url"] == "https://checkout.stripe.test/pay"
            assert create_mock.call_args.args[1] == 15000  # no convenience fee on an event donation
            assert "kind=donation" in create_mock.call_args.args[2]
            assert EventContribution.query.one().status == "pending"
            client.post("/api/payments/vipps-return", json={"reference": "cs_test_1"})
        contribution = EventContribution.query.one()
        assert contribution.status == "paid" and Payment.query.one().status == "paid"


def _session_params(tax_code: str) -> dict:
    from unittest.mock import MagicMock

    client = stripe_gateway.StripeClient(credentials.StripeCredentials(KEY, WHSEC, tax_code=tax_code))
    sessions = MagicMock()
    sessions.create.return_value = MagicMock(id="cs_1", url="https://checkout.stripe.test/pay")
    client._client = MagicMock()
    client._client.v1.checkout.sessions = sessions
    with patch("app.common.site.site_currency", return_value="NOK"):
        client.create_payment("PAY-1", 5000, "http://x/return?ref={CHECKOUT_SESSION_ID}", "Tickets")
    return sessions.create.call_args.kwargs["params"]


def test_checkout_without_a_tax_code_turns_managed_payments_off_and_with_one_sends_it():
    app = _app()
    with app.app_context():
        plain = _session_params("")
        assert plain["managed_payments"] == {"enabled": False}
        assert "tax_code" not in plain["line_items"][0]["price_data"]["product_data"]
        coded = _session_params("txcd_10103001")
        assert "managed_payments" not in coded
        assert coded["line_items"][0]["price_data"]["product_data"]["tax_code"] == "txcd_10103001"
        assert "payment_method_types" not in plain  # Stripe no longer accepts it: methods are set in the owner's Stripe dashboard


def test_managed_payments_is_the_owners_choice_and_needs_a_tax_code():
    app = _app(connected=False)
    with app.app_context(), patch.object(stripe_gateway.StripeClient, "check"):
        assert _call(app, "put", json={"secret_key": KEY, "managed_payments": True}).status_code == 400
        assert _call(app, "put", json={"secret_key": KEY, "managed_payments": True, "tax_code": "nope"}).status_code == 400
        assert _call(app, "put", json={"secret_key": KEY, "managed_payments": True, "tax_code": "txcd_10103001"}).status_code == 200
        creds = credentials.get_stripe()
        assert creds.tax_code == "txcd_10103001"
        # unticked: a tax code that is sent along is dropped
        assert _call(app, "put", json={"secret_key": KEY, "tax_code": "txcd_10103001"}).status_code == 200


def test_pressing_back_on_the_card_page_closes_the_session_and_never_refunds():
    app = _app()
    with app.app_context():
        event = _add_event()
        event.ticket_payment_methods = "card,cash"
        tt = _add_type(event.id)
        create, get, can, ref = _patches("EXPIRED")
        with create, get, can as cancel, ref as refund, patch.object(stripe_gateway.StripeClient, "abandon") as abandon:
            _checkout(app, event, tt)
            res = app.test_client().post("/api/payments/vipps-return", json={"reference": "cs_test_1", "cancelled": True})
        assert abandon.call_count == 1 and cancel.call_count == 0 and refund.call_count == 0
        assert res.get_json()["status"] != "paid" and res.get_json()["provider"] == "stripe"
