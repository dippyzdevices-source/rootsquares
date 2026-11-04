"""Tests for payment models (2 tests), e.g. payment can be created without an order for a membership payment; payment allocation links a payment to a membership period."""
from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_payment_can_be_created_without_an_order_for_a_membership_payment():
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        payment = Payment(
            payment_type="membership",
            order_id=None,
            provider="vipps",
            amount=20000,
            currency="NOK",
            status="pending",
        )
        db.session.add(payment)
        db.session.commit()

        saved = Payment.query.one()
        assert saved.order_id is None
        assert saved.payment_type == "membership"
        assert saved.paid_at is None
        db.drop_all()


def test_payment_allocation_links_a_payment_to_a_membership_period():
    from app.auth.models import User
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType
    from app.memberships.models import MembershipPeriod
    from app.payments.models import Payment, PaymentAllocation
    from datetime import date

    app = _new_app()
    with app.app_context():
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

        payment = Payment(payment_type="membership", provider="vipps", amount=20000, status="paid")
        db.session.add(payment)
        db.session.commit()
        allocation = PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=20000)
        db.session.add(allocation)
        db.session.commit()

        saved = PaymentAllocation.query.one()
        assert saved.payment_id == payment.id
        assert saved.membership_period_id == period.id
        assert saved.amount == 20000
        db.drop_all()
