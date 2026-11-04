"""Tests for online payment provider (2 tests), e.g. get online payment provider returns the fake under testing; fake provider start payment marks paid and allocates immediately."""
from datetime import date

from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _make_period_and_payment():
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipPeriod, MembershipType
    from app.payments.models import Payment

    db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
    member = Member(name="Priya Das", email="priya@example.com")
    db.session.add(member)
    db.session.commit()
    membership = Membership(
        member_id=member.id, membership_type="individual", status="active",
        start_date=date(2027, 1, 1),
    )
    db.session.add(membership)
    db.session.commit()
    period = MembershipPeriod(
        membership_id=membership.id, period_start=date(2027, 1, 1),
        period_end=date(2027, 1, 31), label="January 2027", amount=20000,
    )
    db.session.add(period)
    db.session.commit()
    payment = Payment(payment_type="membership", provider="vipps", amount=20000, status="pending")
    db.session.add(payment)
    db.session.commit()
    return payment, [period]


def test_get_online_payment_provider_returns_the_fake_under_testing():
    from app.payments.online_provider import FakeOnlinePaymentProvider, get_online_payment_provider

    app = _new_app()
    with app.app_context():
        provider = get_online_payment_provider("vipps")
        assert isinstance(provider, FakeOnlinePaymentProvider)
        db.drop_all()


def test_fake_provider_start_payment_marks_paid_and_allocates_immediately():
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment, PaymentAllocation
    from app.payments.online_provider import get_online_payment_provider

    app = _new_app()
    with app.app_context():
        payment, periods = _make_period_and_payment()
        provider = get_online_payment_provider("vipps")

        checkout = provider.start_payment(payment, periods, return_url="https://example.com/return")

        assert checkout.already_paid is True
        saved_payment = db.session.get(Payment, payment.id)
        assert saved_payment.status == "paid"
        assert saved_payment.paid_at is not None
        assert saved_payment.provider_transaction_id is not None

        allocations = PaymentAllocation.query.filter_by(payment_id=payment.id).all()
        assert len(allocations) == 1
        assert allocations[0].amount == 20000

        period = db.session.get(MembershipPeriod, periods[0].id)
        assert period.status == "paid"
        assert period.paid_at is not None
        db.drop_all()
