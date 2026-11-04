"""Tests for admin payments routes (21 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _make_paid_membership_payment(member_name="Priya Das", price=200):
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipPeriod, MembershipType
    from app.payments.models import Payment, PaymentAllocation

    type_name = f"type-{member_name}"
    db.session.add(MembershipType(name=type_name, price=price, billing_frequency="monthly"))
    member = Member(name=member_name, email=f"{member_name}@example.com")
    db.session.add(member)
    db.session.commit()
    membership = Membership(
        member_id=member.id, membership_type=type_name, status="active",
        start_date=date(2027, 1, 1),
    )
    db.session.add(membership)
    db.session.commit()
    period = MembershipPeriod(
        membership_id=membership.id, period_start=date(2027, 1, 1),
        period_end=date(2027, 1, 31), label="January 2027", amount=price * 100,
    )
    db.session.add(period)
    db.session.commit()
    payment = Payment(
        payment_type="membership", provider="vipps", amount=price * 100, status="paid",
    )
    db.session.add(payment)
    db.session.commit()
    db.session.add(
        PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=price * 100)
    )
    db.session.commit()
    return payment, period, member


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/payments/export")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments/export", headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/payments/export", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_export_payments_returns_an_xlsx_file():
    from app.events.models import Event
    from app.orders.models import Order
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW + timedelta(days=10))
        db.session.add(event)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.commit()
        db.session.add(Payment(payment_type="event_ticket", order_id=order.id, provider="manual", amount=15000, status="paid"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments/export", headers=_admin_headers()
            )

        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type

        workbook = load_workbook(BytesIO(response.data))
        rows = list(workbook.active.iter_rows(values_only=True))
        assert rows[0][0] == "Reference"
        assert rows[1][1] == "event_ticket"
        assert rows[1][2] == "Priya Das"
        assert rows[1][3] == "BCA-2026-000001"
        assert rows[1][4] == "manual"
        assert rows[1][6] == 150.0
        db.drop_all()


def test_admin_list_payments_rejects_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/payments")
        assert response.status_code == 401
        db.drop_all()


def test_admin_list_payments_rejects_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/payments", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_list_payments_allows_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/payments", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_list_payments_includes_allocations_for_a_membership_payment():
    app = _new_app()
    with app.app_context():
        payment, period, _ = _make_paid_membership_payment()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/payments", headers=_admin_headers())

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payment_type"] == "membership"
        assert len(data["items"][0]["allocations"]) == 1
        assert data["items"][0]["allocations"][0]["label"] == "January 2027"
        db.drop_all()


def test_admin_list_payments_filters_by_payment_type():
    app = _new_app()
    with app.app_context():
        from app.payments.models import Payment

        _make_paid_membership_payment()
        db.session.add(Payment(payment_type="event_ticket", provider="manual", amount=10000, status="paid"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments?payment_type=event_ticket", headers=_admin_headers()
            )

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payment_type"] == "event_ticket"
        db.drop_all()


def test_admin_list_payments_searches_by_member_name():
    app = _new_app()
    with app.app_context():
        _make_paid_membership_payment(member_name="Ritu Sen")
        _make_paid_membership_payment(member_name="Amit Das")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments?q=Ritu", headers=_admin_headers()
            )

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payer_name"] == "Ritu Sen"
        db.drop_all()


def test_admin_list_payments_shows_the_customer_name_and_reference_for_a_ticket_payment():
    from app.events.models import Event
    from app.orders.models import Order
    from app.payments.service import get_payment_provider

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW + timedelta(days=10))
        db.session.add(event)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.flush()
        get_payment_provider().create_payment(order)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/payments", headers=_admin_headers())

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payer_name"] == "Priya Das"
        assert data["items"][0]["payment_reference"] is not None
        assert data["items"][0]["payment_reference"].startswith("PAY-")
        db.drop_all()


def test_admin_list_payments_searches_ticket_payments_by_customer_name():
    from app.events.models import Event
    from app.orders.models import Order
    from app.payments.service import get_payment_provider

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW + timedelta(days=10))
        db.session.add(event)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.flush()
        get_payment_provider().create_payment(order)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments?q=Priya", headers=_admin_headers()
            )

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payer_name"] == "Priya Das"
        db.drop_all()


def test_admin_list_payments_searches_by_payment_reference():
    app = _new_app()
    with app.app_context():
        payment, _period, _member = _make_paid_membership_payment(member_name="Ritu Sen")
        payment.payment_reference = "PAY-2027-000099"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/payments?q=PAY-2027-000099", headers=_admin_headers()
            )

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["payment_reference"] == "PAY-2027-000099"
        db.drop_all()


def test_admin_refund_reverts_membership_periods_to_unpaid():
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment, period, _ = _make_paid_membership_payment()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/payments/{payment.id}/refund",
                json={"reason": "Member paid by mistake"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        refunded = db.session.get(Payment, payment.id)
        assert refunded.status == "refunded"
        reverted_period = db.session.get(MembershipPeriod, period.id)
        assert reverted_period.status == "unpaid"
        assert reverted_period.paid_at is None
        db.drop_all()


def test_admin_refund_rejects_a_payment_that_is_not_paid():
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment = Payment(payment_type="membership", provider="vipps", amount=20000, status="pending")
        db.session.add(payment)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/payments/{payment.id}/refund",
                json={"reason": "test"},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        db.drop_all()


def test_admin_refund_never_deletes_the_payment_row():
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment, _, _ = _make_paid_membership_payment()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/payments/{payment.id}/refund",
                json={"reason": "test"},
                headers=_admin_headers(),
            )

        assert Payment.query.count() == 1
        db.drop_all()


def test_admin_refund_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        payment, _, member = _make_paid_membership_payment()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/payments/{payment.id}/refund",
                json={"reason": "Member paid by mistake"},
                headers=_admin_headers(),
            )

        entry = AuditLog.query.one()
        assert entry.action == "payment_refunded"
        assert entry.target_type == "payment"
        assert entry.target_id == payment.id
        assert "Member paid by mistake" in entry.description
        db.drop_all()


def test_admin_confirm_pending_membership_payment_marks_periods_paid():
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment, period, _ = _make_paid_membership_payment()
        payment.status = "pending"
        period.status = "unpaid"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            ok = client.post(f"/api/admin/payments/{payment.id}/confirm", headers=_admin_headers())
            again = client.post(f"/api/admin/payments/{payment.id}/confirm", headers=_admin_headers())

        assert ok.status_code == 200
        assert again.status_code == 400
        assert db.session.get(Payment, payment.id).status == "paid"
        assert db.session.get(MembershipPeriod, period.id).status == "paid"
        db.drop_all()


def test_admin_reject_pending_membership_payment_keeps_periods_unpaid():
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment, period, _ = _make_paid_membership_payment()
        payment.status = "pending"
        period.status = "unpaid"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/payments/{payment.id}/reject", headers=_admin_headers()
            )

        assert response.status_code == 200
        assert db.session.get(Payment, payment.id).status == "cancelled"
        assert db.session.get(MembershipPeriod, period.id).status == "unpaid"
        db.drop_all()


def test_export_payments_uses_the_same_filters_as_the_list():
    from app.events.models import Event
    from app.orders.models import Order
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW + timedelta(days=10))
        db.session.add(event)
        db.session.commit()
        for number, name, provider, status in (
            ("BCA-2026-000001", "Priya Das", "cash", "paid"),
            ("BCA-2026-000002", "Rohan Sen", "vipps_qr", "pending"),
        ):
            order = Order(order_number=number, event_id=event.id, customer_name=name,
                          customer_email=f"{name.split()[0].lower()}@example.com", total_amount=15000)
            db.session.add(order)
            db.session.commit()
            db.session.add(Payment(payment_type="event_ticket", order_id=order.id, provider=provider, amount=15000, status=status))
        db.session.commit()

        def exported(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/payments/export{query}", headers=_admin_headers())
            assert response.status_code == 200
            return [r[3] for r in list(load_workbook(BytesIO(response.data)).active.iter_rows(values_only=True))[1:]]

        assert sorted(exported("")) == ["BCA-2026-000001", "BCA-2026-000002"]
        assert exported("?provider=cash") == ["BCA-2026-000001"]
        assert exported("?status=pending") == ["BCA-2026-000002"]
        assert exported("?q=rohan") == ["BCA-2026-000002"]
        db.drop_all()


def test_refunding_a_ticket_payment_emails_the_customer_but_a_membership_refund_does_not():
    from app.events.models import Event
    from app.orders.models import Order, OrderItem
    from app.payments.models import Payment
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=NOW + timedelta(days=10))
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id, customer_name="Priya Das",
                      customer_email="priya@example.com", total_amount=15000, payment_status="paid")
        db.session.add(order)
        db.session.commit()
        item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1, unit_price=15000, subtotal=15000)
        db.session.add(item)
        db.session.commit()
        db.session.add(Ticket(order_item_id=item.id, ticket_code="code-1"))
        payment = Payment(payment_type="event_ticket", order_id=order.id, provider="cash", amount=15000, status="paid")
        db.session.add(payment)
        db.session.commit()
        sent = app.extensions["email_service"].sent_emails

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/payments/{payment.id}/refund", json={"reason": "Event changed."}, headers=_admin_headers()
            )

        assert response.status_code == 200
        assert len(sent) == 1
        assert sent[0]["to"] == "priya@example.com"
        assert "refunded" in sent[0]["subject"] and order.order_number in sent[0]["subject"]
        assert "150.00 kr" in sent[0]["html"] and "Event changed." in sent[0]["html"]

        membership_payment, _, _ = _make_paid_membership_payment()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                f"/api/admin/payments/{membership_payment.id}/refund", json={"reason": "test"}, headers=_admin_headers()
            )
        assert len(sent) == 1  # no email for a membership refund
        db.drop_all()
