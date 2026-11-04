"""Tests for vipps app tickets (23 tests), e.g. vipps app checkout charges total plus 5 percent and returns redirect; vipps app checkout leaves no order behind if vipps fails; vipps app checkout unavailable without credentials."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.vipps_helpers import connect_vipps
from app.payments import vipps
from app.payments.models import Payment
from tests.test_orders_checkout import _add_event, _add_type, _valid_payload


def _app(enabled=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        if enabled:
            from app.settings.models import get_site_settings

            get_site_settings().vipps_app_public = True  # admin switch on (the tests' default)
            connect_vipps("x")
            db.session.commit()
    return app


def _patches(state="CREATED"):
    return (
        patch.object(vipps.VippsClient, "create_payment", return_value={"redirectUrl": "https://vipps.test/pay"}),
        patch.object(vipps.VippsClient, "get_payment", return_value={"state": state}),
        patch.object(vipps.VippsClient, "capture", return_value={}),
        patch.object(vipps.VippsClient, "cancel", return_value={}),
    )


def _checkout(app, event, ticket_type, **extra):
    return app.test_client().post(
        "/api/orders", json=_valid_payload(event.id, ticket_type.id, payment_method="vipps_app", **extra)
    )


def test_vipps_app_checkout_charges_total_plus_5_percent_and_returns_redirect():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id, price=15000)
        create, get, cap, can = _patches()
        with create as create_mock, get, cap, can, patch("app.orders.routes.send_order_received_email") as email:
            response = _checkout(app, event, tt)

        assert response.status_code == 201
        data = response.get_json()
        assert data["redirect_url"] == "https://vipps.test/pay"
        assert data["total_amount"] == 30000  # order total stays the base price
        assert data["surcharge_amount"] == 1500
        assert data["payment_status"] == "pending"
        assert create_mock.call_args.args[1] == 31500
        payment = Payment.query.one()
        assert payment.provider == "vipps_app" and payment.status == "initiated"
        assert payment.amount == 31500 and payment.surcharge_amount == 1500
        assert Order.query.one().payment_status == "pending"
        email.assert_not_called()  # no "pay via Vipps QR" mail for an app payment
        db.drop_all()


def test_vipps_app_checkout_leaves_no_order_behind_if_vipps_fails():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        with patch.object(vipps.VippsClient, "create_payment", side_effect=vipps.VippsError("boom")):
            response = _checkout(app, event, tt)
        assert response.status_code == 502
        assert Order.query.count() == 0 and Payment.query.count() == 0
        db.drop_all()


def test_vipps_app_checkout_unavailable_without_credentials():
    from app.orders.models import Order

    app = _app(enabled=False)
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        response = _checkout(app, event, tt)
        assert response.status_code == 503
        assert Order.query.count() == 0
        db.drop_all()


def test_return_marks_order_paid_issues_tickets_once_and_emails():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id, price=15000)
        create, get, cap, can = _patches("AUTHORIZED")
        with create, get, cap as capture_mock, can, patch("app.orders.emails.send_tickets_confirmed_email") as email:
            _checkout(app, event, tt)
            reference = Payment.query.one().provider_transaction_id
            client = app.test_client()
            first = client.post("/api/payments/vipps-return", json={"reference": reference})
            second = client.post("/api/payments/vipps-return", json={"reference": reference})

        assert first.get_json()["status"] == "paid" and second.get_json()["status"] == "paid"
        assert first.get_json()["order_number"].startswith("BCA-")
        assert capture_mock.call_count == 1 and capture_mock.call_args.args[1] == 31500
        order = Order.query.one()
        assert order.payment_status == "paid" and order.order_status == "confirmed"
        assert Ticket.query.count() == 2
        assert email.call_count == 1
        db.drop_all()


def test_return_releases_the_authorisation_if_the_order_was_rejected_meanwhile():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        create, get, cap, can = _patches("AUTHORIZED")
        with create, get, cap as capture_mock, can as cancel_mock:
            _checkout(app, event, tt)
            Order.query.one().payment_status = "rejected"
            db.session.commit()
            reference = Payment.query.one().provider_transaction_id
            res = app.test_client().post("/api/payments/vipps-return", json={"reference": reference})
        assert res.get_json()["status"] == "cancelled"
        capture_mock.assert_not_called()
        cancel_mock.assert_called_once()
        assert Ticket.query.count() == 0
        db.drop_all()


def test_a_failed_vipps_payment_cancels_its_order_and_frees_the_seats():
    from app.orders.models import Order
    from app.tickets.routes import _sold_count

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id, price=15000)
        create, get, cap, can = _patches("ABORTED")
        with create, get, cap, can, patch("app.orders.emails.send_vipps_payment_failed_email") as email:
            _checkout(app, event, tt)
            assert _sold_count(tt.id) == 2  # the pending order holds its seats while the customer is at Vipps
            reference = Payment.query.one().provider_transaction_id
            client = app.test_client()
            res = client.post("/api/payments/vipps-return", json={"reference": reference})
            client.post("/api/payments/vipps-return", json={"reference": reference})
        assert res.get_json()["status"] == "failed"
        assert email.call_count == 1  # told once, even if the return page is opened again
        order = Order.query.one()
        assert order.payment_status == "failed" and order.order_status == "cancelled"
        assert _sold_count(tt.id) == 0
        db.drop_all()


def test_a_failed_vipps_payment_leaves_an_order_the_customer_claimed_as_paid():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        create, get, cap, can = _patches("ABORTED")
        with create, get, cap, can:
            _checkout(app, event, tt)
            Order.query.one().payment_status = "pending_verification"
            db.session.commit()
            reference = Payment.query.one().provider_transaction_id
            app.test_client().post("/api/payments/vipps-return", json={"reference": reference})
        assert Order.query.one().payment_status == "pending_verification"
        db.drop_all()


def test_return_with_unknown_reference_is_404_and_config_endpoint_reports_fee():
    app = _app()
    with app.app_context():
        client = app.test_client()
        assert client.post("/api/payments/vipps-return", json={"reference": "nope"}).status_code == 404
        cfg = client.get("/api/payments/vipps-app").get_json()
        assert cfg == {"enabled": True, "surcharge_percent": 5}
        db.drop_all()


def test_admin_mark_paid_cancels_an_open_vipps_attempt_instead_of_confirming_it():
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        create, get, cap, can = _patches()
        with create, get, cap as capture_mock, can as cancel_mock:
            order_id = _checkout(app, event, tt).get_json()["id"]
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                res = app.test_client().post(f"/api/admin/orders/{order_id}/mark-paid", headers=auth_header(admin_token))
        assert res.status_code == 200
        assert Payment.query.one().status == "cancelled"
        cancel_mock.assert_called_once()
        capture_mock.assert_not_called()
        db.drop_all()


def test_sweep_confirms_old_initiated_payments_but_skips_fresh_ones():
    from datetime import datetime, timedelta, timezone

    from app.orders.models import Order

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        create, get, cap, can = _patches("AUTHORIZED")
        with create, get, cap, can, patch("app.orders.emails.send_tickets_confirmed_email"):
            _checkout(app, event, tt)
            payment = Payment.query.one()

            # Fresh (just created): left alone — the customer is probably still at Vipps.
            assert vipps.sweep_initiated_payments() == 0
            assert db.session.get(Payment, payment.id).status == "initiated"

            payment.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            db.session.commit()
            assert vipps.sweep_initiated_payments() == 1

        assert db.session.get(Payment, payment.id).status == "paid"
        assert Order.query.one().payment_status == "paid"
        assert vipps.sweep_initiated_payments() == 0  # nothing left "initiated"
        db.drop_all()


def test_admin_vipps_check_confirms_a_stuck_payment_and_rejects_other_providers():
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        create, get, cap, can = _patches("AUTHORIZED")
        with create, get, cap, can, patch("app.orders.emails.send_tickets_confirmed_email"):
            _checkout(app, event, tt)
            payment_id = Payment.query.one().id
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                client = app.test_client()
                res = client.post(f"/api/admin/payments/{payment_id}/vipps-check", headers=auth_header(admin_token))
                manual = Payment(payment_type="membership", provider="vipps", amount=100, status="pending")
                db.session.add(manual)
                db.session.commit()
                other = client.post(f"/api/admin/payments/{manual.id}/vipps-check", headers=auth_header(admin_token))
        assert res.status_code == 200 and res.get_json()["status"] == "paid"
        assert other.status_code == 404
        db.drop_all()


def test_customers_cannot_use_vipps_app_until_it_is_made_public_but_credentials_still_enable_admin_test():
    from app.orders.models import Order
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app()
    with app.app_context():
        from app.settings.models import get_site_settings

        get_site_settings().vipps_app_public = False  # credentials set, admin switch off
        db.session.commit()
        event = _add_event()
        tt = _add_type(event.id)
        client = app.test_client()
        assert client.get("/api/payments/vipps-app").get_json()["enabled"] is False
        assert _checkout(app, event, tt).status_code == 503
        assert Order.query.count() == 0

        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        create, get, cap, can = _patches("AUTHORIZED")
        with create as create_mock, get, cap as capture_mock, can:
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                started = client.post("/api/admin/payments/vipps-test", headers=auth_header(admin_token))
            assert started.status_code == 201
            body = started.get_json()
            assert body["redirect_url"] == "https://vipps.test/pay"
            assert body["payment"]["amount"] == 105  # 1 kr + 5% convenience fee
            assert body["payment"]["payment_type"] == "vipps_test"
            assert body["payment"]["payer_name"] == "Vipps test payment (admin)"
            assert create_mock.call_args.args[1] == 105
            reference = Payment.query.one().provider_transaction_id
            res = client.post("/api/payments/vipps-return", json={"reference": reference})
        assert res.get_json() == {"status": "paid", "order_number": None, "provider": "vipps_app"}
        capture_mock.assert_called_once()

        # Once Vipps App is public the test payment is retired (and the status endpoint says so).
        get_site_settings().vipps_app_public = True
        db.session.commit()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            status = client.get("/api/admin/payments/vipps-status", headers=auth_header(admin_token)).get_json()
            again = client.post("/api/admin/payments/vipps-test", headers=auth_header(admin_token))
        assert status == {"configured": True, "public": True}
        assert again.status_code == 409
        db.drop_all()


def test_admin_vipps_test_payment_requires_admin_and_credentials():
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app(enabled=False)
    with app.app_context():
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        _, member_token = make_user_and_token(email="m@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            assert client.post("/api/admin/payments/vipps-test").status_code == 401
            assert client.post("/api/admin/payments/vipps-test", headers=auth_header(member_token)).status_code == 403
            assert client.post("/api/admin/payments/vipps-test", headers=auth_header(admin_token)).status_code == 503
        db.drop_all()


def test_admin_can_switch_vipps_app_on_for_customers_in_settings_and_it_is_audited():
    from app.audit.models import AuditLog
    from app.settings.models import get_site_settings
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app()
    with app.app_context():
        get_site_settings().vipps_app_public = False
        db.session.commit()
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        _, member_token = make_user_and_token(email="m@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            assert client.get("/api/admin/settings", headers=auth_header(admin_token)).get_json()["vipps_app_public"] is False
            assert "vipps_app_public" not in client.get("/api/settings").get_json()  # not public
            assert client.patch("/api/admin/settings", json={"vipps_app_public": True}, headers=auth_header(member_token)).status_code == 403
            assert client.patch("/api/admin/settings", json={"vipps_app_public": "yes"}, headers=auth_header(admin_token)).status_code == 400
            res = client.patch("/api/admin/settings", json={"vipps_app_public": True}, headers=auth_header(admin_token))
            assert res.get_json()["vipps_app_public"] is True
            assert client.get("/api/payments/vipps-app").get_json()["enabled"] is True
        assert "Vipps-App payments ON" in AuditLog.query.order_by(AuditLog.id.desc()).first().description
        db.drop_all()


def _paid_manual_ticket_order(app, event_start=None):
    """A manual-payment order marked paid by an admin (so it has a paid Payment + valid tickets)."""
    from datetime import datetime, timedelta, timezone

    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    kwargs = {"start_datetime": event_start} if event_start else {}
    event = _add_event(**kwargs)
    tt = _add_type(event.id, price=15000)
    _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
    client = app.test_client()
    order_id = client.post("/api/orders", json=_valid_payload(event.id, tt.id)).get_json()["id"]
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()), patch(
        "app.orders.admin_routes.send_tickets_confirmed_email"
    ):
        client.post(f"/api/admin/orders/{order_id}/mark-paid", headers=auth_header(admin_token))
    return order_id, admin_token


def _refund(app, admin_token, payment_id):
    from tests.auth_helpers import auth_header, FakeJWKClient

    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().post(
            f"/api/admin/payments/{payment_id}/refund", json={}, headers=auth_header(admin_token)
        )


def test_refunding_a_manual_ticket_payment_cancels_the_order_and_voids_tickets_without_calling_vipps():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        order_id, admin_token = _paid_manual_ticket_order(app)
        payment = Payment.query.one()
        payment.status = "paid"  # manual confirm already flips it; make the precondition explicit
        db.session.commit()
        with patch.object(vipps.VippsClient, "refund") as refund_mock:
            res = _refund(app, admin_token, payment.id)
        assert res.status_code == 200
        assert res.get_json()["refund_mode"] == "manual"
        refund_mock.assert_not_called()  # manual: the association returns the money itself
        order = db.session.get(Order, order_id)
        assert order.payment_status == "cancelled" and order.order_status == "cancelled"
        assert {t.status for t in Ticket.query.all()} == {"void"}
        db.drop_all()


def test_refund_is_blocked_after_the_event_day():
    from datetime import datetime, timedelta, timezone

    app = _app()
    with app.app_context():
        # Ticket sale needs an upcoming event, so create it upcoming, then move it into the past.
        order_id, admin_token = _paid_manual_ticket_order(app)
        from app.events.models import Event

        event = Event.query.one()
        event.start_datetime = datetime.now(timezone.utc) - timedelta(days=3)
        db.session.commit()
        payment = Payment.query.one()
        res = _refund(app, admin_token, payment.id)
        assert res.status_code == 400 and "after the event day" in res.get_json()["error"]
        assert db.session.get(Payment, payment.id).status == "paid"
        db.drop_all()


def test_refund_is_blocked_when_a_ticket_was_already_used():
    from app.tickets.models import Ticket

    app = _app()
    with app.app_context():
        _, admin_token = _paid_manual_ticket_order(app)
        Ticket.query.first().status = "used"
        db.session.commit()
        res = _refund(app, admin_token, Payment.query.one().id)
        assert res.status_code == 400 and "already been used" in res.get_json()["error"]
        db.drop_all()


def test_payments_list_reports_refund_mode_and_block_reason():
    from tests.auth_helpers import auth_header, FakeJWKClient

    app = _app()
    with app.app_context():
        _, admin_token = _paid_manual_ticket_order(app)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            item = app.test_client().get("/api/admin/payments", headers=auth_header(admin_token)).get_json()["items"][0]
        assert item["refund_mode"] == "manual" and item["refund_blocked_reason"] is None
        db.drop_all()


def test_order_detail_lists_its_payments_and_the_payment_list_names_the_order():
    from tests.auth_helpers import auth_header, FakeJWKClient

    app = _app()
    with app.app_context():
        order_id, admin_token = _paid_manual_ticket_order(app)
        payment = Payment.query.one()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            order = client.get(f"/api/admin/orders/{order_id}", headers=auth_header(admin_token)).get_json()
            listed = client.get("/api/admin/payments", headers=auth_header(admin_token)).get_json()["items"][0]
        assert [p["id"] for p in order["payments"]] == [payment.id]
        assert order["payments"][0]["provider"] == "vipps_qr"
        assert listed["order_id"] == order_id and listed["order_number"] == order["order_number"]
        db.drop_all()


def test_event_payment_method_setting_is_enforced_at_checkout_and_reported_publicly():
    from app.orders.models import Order

    app = _app()
    with app.app_context():
        qr_only = _add_event(slug="qr-only", ticket_payment_methods="qr")
        app_only = _add_event(slug="app-only", ticket_payment_methods="app")
        both = _add_event(slug="both-ways")
        tt_qr, tt_app, tt_both = (_add_type(e.id) for e in (qr_only, app_only, both))
        client = app.test_client()

        assert client.get("/api/events/qr-only").get_json()["payment_methods"] == ["qr"]
        assert client.get("/api/events/app-only").get_json()["payment_methods"] == ["app"]
        assert sorted(client.get("/api/events/both-ways").get_json()["payment_methods"]) == ["app", "qr"]

        # QR-only event refuses the Vipps App; app-only refuses the (default) QR flow.
        create, get, cap, can = _patches()
        with create, get, cap, can:
            res = _checkout(app, qr_only, tt_qr)
            assert res.status_code == 400 and "payment_method" in res.get_json()["errors"]
            plain = client.post("/api/orders", json=_valid_payload(app_only.id, tt_app.id))
            assert plain.status_code == 400 and "payment_method" in plain.get_json()["errors"]
            assert _checkout(app, app_only, tt_app).status_code == 201
            assert client.post("/api/orders", json=_valid_payload(both.id, tt_both.id)).status_code == 201
            assert _checkout(app, both, tt_both).status_code == 201
        assert Order.query.count() == 3  # the two refused attempts created nothing
        db.drop_all()


def test_app_only_event_falls_back_to_cash_while_vipps_app_is_not_switched_on():
    from app.settings.models import get_site_settings

    app = _app()
    with app.app_context():
        get_site_settings().vipps_app_public = False
        db.session.commit()
        event = _add_event(ticket_payment_methods="app")
        tt = _add_type(event.id)
        client = app.test_client()
        assert client.get("/api/events/durga-puja-2026").get_json()["payment_methods"] == ["cash"]
        assert client.post("/api/orders", json=_valid_payload(event.id, tt.id)).status_code == 400  # the default method (Vipps QR) is not offered here
        assert client.post("/api/orders", json=_valid_payload(event.id, tt.id, payment_method="cash")).status_code == 201
        db.drop_all()


def test_admin_event_payment_methods_validated_and_copied_by_duplicate():
    from tests.auth_helpers import auth_header, make_user_and_token, FakeJWKClient

    app = _app()
    with app.app_context():
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        payload = {"title": "Mahalaya", "slug": "mahalaya", "event_type": "festival", "start_datetime": "2027-10-10T16:00:00+00:00"}
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            h = auth_header(admin_token)
            created = client.post("/api/admin/events", json=payload, headers=h).get_json()
            assert created["ticket_payment_methods"] == "qr,app"
            assert client.patch(f"/api/admin/events/{created['id']}", json={"ticket_payment_methods": "bitcoin"}, headers=h).status_code == 400
            patched = client.patch(f"/api/admin/events/{created['id']}", json={"ticket_payment_methods": "qr"}, headers=h).get_json()
            assert patched["ticket_payment_methods"] == "qr"
            copy = client.post(f"/api/admin/events/{created['id']}/duplicate", headers=h).get_json()
            assert copy["ticket_payment_methods"] == "qr"
        db.drop_all()


def test_the_payment_failed_email_says_nothing_was_charged_and_links_back_to_the_event():
    from app.email.templates import render_vipps_payment_failed_email

    class _O:
        customer_name = "Asha"
        order_number = "BCA-2026-000300"

    class _E:
        title = "Durga Puja 2026"

    html_out, text, _ = render_vipps_payment_failed_email(order=_O(), event=_E(), retry_url="https://bca.test/events/durga")
    assert "BCA-2026-000300" in html_out and "not been charged" in html_out
    assert "https://bca.test/events/durga" in html_out and "https://bca.test/events/durga" in text
