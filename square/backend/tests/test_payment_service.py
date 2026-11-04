"""Tests for payment service (3 tests), e.g. create payment produces a pending manual payment; confirm payment marks it paid; get payment provider returns a manual provider."""
from datetime import datetime, timezone

from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _make_order():
    from app.events.models import Event
    from app.orders.models import Order

    event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                  start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
    db.session.add(event)
    db.session.commit()
    order = Order(order_number="BCA-2026-000001", event_id=event.id,
                  customer_name="Priya Das", customer_email="priya@example.com",
                  total_amount=30000)
    db.session.add(order)
    db.session.commit()
    return order


def test_create_payment_produces_a_pending_manual_payment():
    from app.payments.models import Payment
    from app.payments.service import ManualPaymentProvider

    app = _new_app()
    with app.app_context():
        order = _make_order()
        provider = ManualPaymentProvider()

        payment = provider.create_payment(order)
        db.session.commit()

        assert payment.order_id == order.id
        assert payment.provider == "vipps_qr"
        assert payment.amount == 30000
        assert payment.currency == "NOK"
        assert payment.status == "pending"
        assert payment.payment_reference == f"PAY-{payment.created_at.year}-{payment.id:06d}"
        assert Payment.query.count() == 1
        db.drop_all()


def test_confirm_payment_marks_it_paid():
    from app.payments.service import ManualPaymentProvider

    app = _new_app()
    with app.app_context():
        order = _make_order()
        provider = ManualPaymentProvider()
        payment = provider.create_payment(order)
        db.session.commit()

        provider.confirm_payment(payment)
        db.session.commit()

        assert payment.status == "paid"
        db.drop_all()


def test_get_payment_provider_returns_a_manual_provider():
    from app.payments.service import ManualPaymentProvider, get_payment_provider

    app = _new_app()
    with app.app_context():
        assert isinstance(get_payment_provider(), ManualPaymentProvider)
        db.drop_all()
